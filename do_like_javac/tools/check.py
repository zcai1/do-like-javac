# DEPRECATED -- WILL BE REMOVED IN FUTURE VERSION

import os
import pprint
import argparse

from . import common

argparser = argparse.ArgumentParser(add_help=False)
check_group = argparser.add_argument_group('checker-framework tool arguments')

check_group.add_argument('--stubs', metavar='<stubs>',
                         action='store', help='stub files to use')

def run(args, javac_commands, jars):
    for jc in javac_commands:
        pprint.pformat(jc)

        class_path = jc['javac_switches']['classpath']

        cmd = get_tool_command(args, class_path, jc['java_files'])

        common.run_cmd(cmd, args, 'check')

def get_tool_command(args, target_classpath, java_files):
    # checker-framework javac.
    if 'CLASSPATH' in os.environ:
            target_classpath += ':' + os.environ['CLASSPATH']

    javacheck = os.path.join(os.path.split(os.path.realpath(__file__))[0], "../../../", "checker-framework/checker/bin/javac")
    checker_command = [javacheck,
                       "-processor", args.checker,
                       "-classpath", target_classpath]
    if args.stubs:
        checker_command += ["-Astubs={}".format(args.stubs)]

    checker_command.extend(java_files)

    return checker_command
