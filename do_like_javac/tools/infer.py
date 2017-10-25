import os
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

def run(args, javac_commands, jars):
    print os.environ
    for jc in javac_commands:
        cmd = get_tool_command(args, jc['javac_switches']['classpath'], jc['java_files'])
        common.run_cmd(cmd, args, 'infer')

def get_tool_command(args, target_classpath, java_files):
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
                             '--logLevel=WARNING',
                             '-afud', args.afuOutputDir]
    CFI_command.extend(java_files)

    return CFI_command

