import os,sys
import argparse
import subprocess

from . import common

argparser = argparse.ArgumentParser(add_help=False)
infer_group = argparser.add_argument_group('inference tool arguments')

infer_group.add_argument('-s', '--solver', metavar='<solver>',
                        action='store',default='checkers.inference.solver.DebugSolver',
                        help='solver to use on constraints')
infer_group.add_argument('-afud', '--afuOutputDir', metavar='<afud>',
                        action='store',default='afud/',
                        help='Annotation File Utilities output directory')
infer_group.add_argument('-m', '--mode', metavar='<mode>',
                        action='store',default='INFER',
                        help='Modes of operation: TYPECHECK, INFER, ROUNDTRIP,ROUNDTRIP_TYPECHECK')
infer_group.add_argument('-solverArgs', '--solverArgs', metavar='<solverArgs>',
                        action='store',default='backEndType=maxsatbackend.MaxSat',
                        help='arguments for solver')
infer_group.add_argument('-cfArgs', '--cfArgs', metavar='<cfArgs>',
                        action='store',default='',
                        help='arguments for checker framework')
infer_group.add_argument('--inPlace', action='store_true',
                        help='Whether or not the annoations should be inserted in the original source code')
infer_group.add_argument('--crashExit', action='store_true',
                        help='set it then dljc will early exit if it found a round of inference crashed during the iteration.')

def run(args, javac_commands, jars):
    print(os.environ)
    idx = 0
    for jc in javac_commands:
        jaif_file = "logs/infer_result_{}.jaif".format(idx)
        cmd = get_tool_command(args, jc['javac_switches']['classpath'], jc['java_files'], jaif_file)
        status = common.run_cmd(cmd, args, 'infer')
        if args.crashExit and not status['return_code'] == 0:
            print("----- CF Inference/Typecheck crashed! Terminates DLJC. -----")
            sys.exit(1)
        idx += 1

def get_tool_command(args, target_classpath, java_files, jaif_file="default.jaif"):
    # the dist directory of CFI.
    CFI_dist = os.path.join(os.path.split(os.path.realpath(__file__))[0], "../../../", 'checker-framework-inference', 'dist')
    CFI_command = ['java']

    java_version = subprocess.check_output(["java", "-version"], stderr=subprocess.STDOUT)
    # Compatible with Python3. In Python 2.7, type(java_version) == str; but in Python3, type(java_version) == bytes.
    # After do-like-javac updates to Python 3, this code can still work.
    if isinstance(java_version, bytes):
        java_version = java_version.decode("utf-8")
    # java_version is a String like this:
    # 'openjdk version "1.8.0_222"
    # OpenJDK Runtime Environment (build 1.8.0_222-8u222-b10-1ubuntu1~19.04.1-b10)
    # OpenJDK 64-Bit Server VM (build 25.222-b10, mixed mode)
    # '
    # We need to extract the version number from this String.
    # split_version_number is a list of split version numbers in String type, e.g., ["1", "8", "0_222"].
    # For Java 9+, it can simply be ["9"]. So in this case we should compare the first element directly.
    split_version_number = []
    for each_line in java_version.splitlines():
        if each_line.startswith('openjdk version') or each_line.startswith('java version'):
            split_version_number = each_line.split()[2].strip('"').split(".")
            break
    assert len(split_version_number) >= 1, 'No openjdk version info found. java_version: {}'.format(java_version)
    is_jvm8 = split_version_number[0] == "8" if len(split_version_number) == 1 else split_version_number[1] == "8"
    if is_jvm8:
        print('Using Java 8, runtime bcp will be added.')
        CFI_command += ['-DInferenceLauncher.runtime.bcp=' + os.path.join(CFI_dist, "javac.jar")]

    cp = target_classpath + \
             ':' + os.path.join(CFI_dist, 'checker.jar') + \
             ':' + os.path.join(CFI_dist, 'plume.jar') + \
             ':' + os.path.join(CFI_dist, 'com.microsoft.z3.jar') + \
             ':' + os.path.join(CFI_dist, 'checker-framework-inference.jar')

    if 'CLASSPATH' in os.environ:
        cp += ':' + os.environ['CLASSPATH']

        # os env classpath must be added to targetclasspath for running CFI in
        # typecheck mode
        target_classpath += ':' + os.environ['CLASSPATH']
        # TODO: see if this is still needed:
        # env_classpath must also have a project's dependent jars
        # os.environ['CLASSPATH'] = target_classpath

    CFI_command += [        # '-p', # printCommands before executing
                            '-classpath', cp,
                            'checkers.inference.InferenceLauncher']

    if not args.cfArgs == "":
        CFI_command += [    '--cfArgs', args.cfArgs]

    CFI_command += [        '--checker', args.checker,
                            '--solver', args.solver,
                            '--solverArgs', args.solverArgs,
                            '--mode', args.mode,
                            '--hacks=true',
                            '--targetclasspath', target_classpath,
                            '--logLevel=INFO',
                            '--jaifFile', jaif_file]

    if args.inPlace:
        CFI_command += ['--inPlace=true']
    else:
        CFI_command += ['-afud', args.afuOutputDir]

    CFI_command.extend(java_files)

    return CFI_command

