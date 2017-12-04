import os,sys
import argparse
import common

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
    print os.environ
    idx = 0
    for jc in javac_commands:
        jaif_file = "logs/infer_result_{}.jaif".format(idx)
        cmd = get_tool_command(args, jc['javac_switches']['classpath'], jc['java_files'], jaif_file)
        status = common.run_cmd(cmd, args, 'infer')
        if args.crashExit and not status['return_code'] == 0:
            print "----- CF Inference crashed! Terminates DLJC. -----"
            sys.exit(1)
        idx += 1

def get_tool_command(args, target_classpath, java_files, jaif_file="default.jaif"):
    # the dist directory of CFI.
    CFI_dist = os.path.join(os.environ['JSR308'], 'checker-framework-inference', 'dist')
    CFI_command = ['java']

    cp = target_classpath + \
             ':' + os.path.join(CFI_dist, 'checker.jar') + \
             ':' + os.path.join(CFI_dist, 'plume.jar') + \
             ':' + os.path.join(CFI_dist, 'checker-framework-inference.jar')

    if 'CLASSPATH' in os.environ:
        cp += ':' + os.environ['CLASSPATH']

    CFI_command += ['-classpath', cp,
                             'checkers.inference.InferenceLauncher',
                             '--solverArgs', args.solverArgs,
                             '--cfArgs', args.cfArgs,
                             '--checker', args.checker,
                             '--solver', args.solver,
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

