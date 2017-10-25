# DEPRECATED -- WILL BE REMOVED IN FUTURE VERSION

import common
import os
import pprint

argparser = None

def run(args, javac_commands, jars):
    for jc in javac_commands:
        pprint.pformat(jc)
        cmd = get_tool_command(args, jc['javac_switches']['classpath'], jc['java_files'])
        common.run_cmd(cmd, args, 'check')

def get_tool_command(args, target_classpath, java_files):
    # checker-framework javac.
    javacheck = os.environ['JSR308']+"/checker-framework/checker/bin/javac"
    checker_command = [javacheck,
                       "-processor", args.checker,
                       "-classpath", target_classpath]
    checker_command.extend(java_files)

    return checker_command
