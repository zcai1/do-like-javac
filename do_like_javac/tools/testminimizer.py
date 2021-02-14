import argparse, math
import os, shutil
from shutil import copy2
from os.path import basename
import re
from . import (common, infer, check)

import lithium

argparser = argparse.ArgumentParser(add_help=False)

test_minimizer_group = argparser.add_argument_group('test minimizer arguments')

test_minimizer_group.add_argument('--annotationClassPath', metavar='<annotationClassPath>',
                        action='store',default='',
                        help='external annotation classpath')

test_minimizer_group.add_argument('--debugByteCodeDir', metavar='<debugByteCodeDir>',
                        action='store',default=os.path.join(os.getcwd(), 'inferDebugBuild'),
                        help='project debugging byte code directory')

test_minimizer_group.add_argument('--testCaseDir', metavar='<testCaseDir>',
                        action='store',default=os.path.join(os.getcwd(), 'deltaTestCase'),
                        help='directory to store minimized test case')

test_minimizer_group.add_argument('--debuggedTool', metavar='<debuggedTool>',
                        action='store',default='inference',
                        choices=set(('inference', 'check')),
                        help='the traget tool need to debug')

test_minimizer_group.add_argument('--expectReturnCode', metavar='<outputRegex>',
                        action='store',default=1,
                        help='the expected return code of debugged tool.')

test_minimizer_group.add_argument('--expectOutputRegex', metavar='<outputRegex>',
                        action='store',default=None,
                        help='the regular expression of expected out put of debugged tool.')

test_minimizer_group.add_argument('--onlyCompileBytecodeBase', metavar='<onlyCompileBytecodeBase>',
                                type=bool, default=False,
                                help='Whether only compile a project byte code base without finding file set.')

#Support tools need to implement below method:
# function name: get_tool_command
# input: (args, targetProjectByteCodeDir, targetJavaFiles)
# output: the tool command that running 'tool' with 'args' on 'targetJavaFiles'
#         based on project bytecode in 'targetProjectByteCodeDir'
SUPPORT_TOOLS = {
    'check': check,
    'inference': infer,
}


## Debug script for finding a minimum test case that exposes a tool bug (crash).
#
# Support debugged tools: checker-framework, checker-framework-inference.
#
# This script will build a bytecode base for the target project,
# then running debugged tool by applying delta debugging algorithm,
# try to minimize an interesting smallest file set first, then try to minimize
# each file within that file set. Finally, it terminates on either found
# a first tool bug (crash) or when it finished the delta debugging searching.


def run(args, javac_commands, jars):
    print("------ Running debugging script ------")

    if not args.debuggedTool in SUPPORT_TOOLS:
        print("ERROR: Could not find tool {} in support tools.".format(args.debuggedTool))
        return None

    # Create bytecode output directory, if not exist.
    if not os.path.exists(args.debugByteCodeDir):
        os.mkdir(args.debugByteCodeDir)

    javac_command = ['javac']
    # The source file list of the target project, extracted by do-like-javac.
    java_files_list = list()

    target_total_cp = ""

    # Build initial bytecode base for target project.
    for jc in javac_commands:
        target_cp = jc['javac_switches']['classpath']
        cp = target_cp
        if (not args.annotationClassPath is None):
            cp += ":" + args.annotationClassPath

        cmd = javac_command + ['-classpath', cp,
                               '-d', args.debugByteCodeDir]
        cmd.extend(jc['java_files'])
        common.run_cmd(cmd, args, 'compileByteCodeBase')

        # Collect java files of target project for debugging.
        java_files_list.extend(jc['java_files'])
        target_total_cp += target_cp

    if args.onlyCompileBytecodeBase:
        print("Succeed built project bytecode in directory {}.".format(args.debugByteCodeDir))
        return None

    # Compute the classpath for compiling test files. (need this to test compilability of a reduced file)
    classpath = args.debugByteCodeDir if args.annotationClassPath is None else args.debugByteCodeDir + ":" + args.annotationClassPath
    classpath = target_total_cp + ":" + classpath

    # Initialize Interesting Judger.
    InterestingJudger.expect_return_code = int(args.expectReturnCode)
    if args.expectOutputRegex:
        InterestingJudger.output_regex = re.compile(args.expectOutputRegex)

    # Minimizing file set.
    minimized_file_set = FileSetMinimization(args, classpath).run(java_files_list)
    if len(minimized_file_set) < 1:
        print("---- Do not found any thing interesting. ----")
    else:
        # Create test case directory, if not exist.
        if not os.path.exists(args.testCaseDir):
            os.mkdir(args.testCaseDir)
            print("---- Created test case directory: {}".format(args.testCaseDir))



        test_files = list()
        print("---- copying files to test case directory {} ----".format(args.testCaseDir))
        for source_file in minimized_file_set:
            copy2(source_file, args.testCaseDir)
            test_files.append(os.path.join(args.testCaseDir, basename(source_file)))
        print("--- copy done ----")

        for test_file in test_files:
            together_java_files = ListUtil.get_complement_list(list(test_file), test_files)
            FileMinimization.run(args, classpath, test_file, together_java_files)

    print("------ Debugging script finished ------")

class InterestingJudger(object):
    expect_return_code = 1
    output_regex = None

    @staticmethod
    def interesting(exec_status):
        """
        Deciding if a test case is interesting by giving the tool execution status.
        """

        match_rtn_code = (exec_status['return_code'] == InterestingJudger.expect_return_code)
        exist_regex = bool(InterestingJudger.output_regex)
        if exist_regex:
            match_regex = bool(InterestingJudger.output_regex.search(exec_status['output']))
        else:
            # Set match_regex to True if no regex exist.
            match_regex = True
        is_interesting = match_rtn_code and match_regex
        # print("rtn_code match: {}, exist_regex: {}, match_regex: {}, is_interesting: {}.".format(match_rtn_code, exist_regex, match_regex, is_interesting))
        return is_interesting

class FileMinimization(object):
    """
    Class for performing minimization on file level.

    Given a java file, it try to minimize it to an local 1-minimal file
    that still trigger the tool crash.
    """

    @staticmethod
    def run(args, classpath, java_file, together_java_files):
        """
        Main entry of the file minimization.

        @param args args parsed by ArgumentParser, used to running debugged tool
        @param classpath the necessary classpath to compile the given java_file
        @param java_file the java file that need to be minimized
        @param together_java_files files that need to run with the given java_file to trigger tool crash
        """

        print("====== Minimizing file {} ======".format(java_file))
        FileMinimization.preprocess(java_file)

        l = lithium.Lithium()
        l.conditionArgs = args
        l.conditionScript = FileInterestingJudger(java_file, together_java_files, classpath)
        l.testcase = lithium.TestcaseLine()
        l.testcase.readTestcase(java_file)

        # First round of reduction by main minimization algorithm
        print("====== Performing main minimization algorithm ======")
        l.strategy = lithium.Minimize()
        l.run()
        print("------ main minimization algorithm done ------")

        # Second round of reduction, focus on reducing balanced pairs
        print("====== Minimizing balanced pairs ======")
        l.strategy = lithium.MinimizeBalancedPairs()
        l.run()
        print("------ Minimizing balanced pairs done ------")
        # Third round ofreduction, reducing surrounding pairs
        print("====== Minimizing surrounding pairs ======")
        l.strategy = lithium.MinimizeSurroundingPairs()
        l.run()
        print("------ Minimizing surrounding pairs done ------")

        # Final round of reduction, repeat the main minimization algorithm
        print("====== Performing main minimization algorithm ======")
        l.strategy = lithium.Minimize()
        l.run()
        print("------ main minimization algorithm done ------")
        print("------ file {} has been minimized ------".format(java_file))

    @staticmethod
    def preprocess(java_file):
        """
        Remove all comment lines, empty lines in the given java_file.
        This coulde reduce the searching space for file minimization.
        """
        print("==== Preprocess: removing comments and empty lines in file {} ====".format(java_file))
        # First remove all comments.
        with open(java_file, 'r') as read_file:
            file_chars = read_file.read()
            write_chars = list()
            idx = 0
            while idx < len(file_chars):
                if file_chars[idx] == '/' and idx < len(file_chars) - 1:
                    next_char = file_chars[idx + 1]
                    if next_char == '/':
                        # Jump to the char next to the 2nd '/'.
                        idx = idx + 2
                        while idx < len(file_chars) - 1:
                            if file_chars[idx] == '\n':
                                # Exits loop with idx pointing to the next char after the comment.
                                idx = idx + 1
                                break
                            idx = idx + 1
                        continue
                    elif next_char == '*':
                        # Jump to the char next to '*'.
                        idx = idx + 2
                        while idx < len(file_chars) - 1:
                            if file_chars[idx] == '*' and file_chars[idx + 1] == '/':
                                # Exits loop with idx pointing to the next char after the comment.
                                idx = idx + 2
                                break
                            idx = idx + 1
                        continue
                write_chars.append(file_chars[idx])
                idx = idx + 1

        with open(java_file, 'w') as write_file:
            write_file.write(''.join(write_chars))

        # Then remove all empty lines.
        # (Since remove comments may also generate new empty lines,
        # removing empty lines in a second iteration will make sure
        # all empty lines be removed.)
        with open(java_file, 'r') as read_file:
            write_lines = list()
            for line in read_file.readlines():
                if line.strip() == '':
                    continue
                write_lines.append(line)

        with open(java_file, 'w') as write_file:
            write_file.write(''.join(write_lines))
        print("---- Preprocess done ----")

class FileInterestingJudger(object):
    """
    Class for deciding if a reduced file is interesting.

    This class is an implementation of conditionScript for Lithium:
    https://github.com/MozillaSecurity/lithium/blob/master/src/lithium/docs/creating-tests.md
    """

    def __init__ (self, test_file, together_java_files, target_classpath):
        self.test_file = test_file
        self.target_classpath = target_classpath
        self.together_java_files = together_java_files

    def init(self, args):
        pass

    def interesting(self, args, tempPrefix):
        testcase_lines = None
        with open(self.test_file, 'r') as testcase:
            testcase_lines = len(testcase.readlines())

        if not ToolRunningUtil.compilable(args, self.test_file, self.target_classpath):
            return False

        java_files = [self.test_file,]

        java_files.extend(self.together_java_files)

        exec_result = ToolRunningUtil.running_tool(args, java_files, self.target_classpath, "single-file-minimization")

        # Delegate to InterestingJudger to decide if current test case is interesting.
        is_interesting = InterestingJudger.interesting(exec_result)
        print("Current file lines: {}, Pass compile. Is Interesting: {}.".format(testcase_lines, is_interesting))
        return is_interesting

    def cleanup(self, conditionArgs):
        pass


class FileSetMinimization(object):
    """
    File set minimization class.

    It perform minimization on set level, i.e. minimized a given file set to
    a 1-minimal file set.
    """

    def __init__(self, tool_args, target_classpath):
        self.tool_args = tool_args
        self.target_classpath = target_classpath

    def run(self, file_list):
        print("====== Minimizing file set ======")
        minimized_file_set = self.minimize_file_set(file_list, 2)
        if len(minimized_file_set) > 0:
            print("======== BREAK POINT ======")
            print("Found a minimized file set: {}.".format(minimized_file_set))
        else:
            print("Does not found a minimized file set.")
        return minimized_file_set
        print("------ Minimize file set done ------")

    def minimize_file_set(self, file_list, n):
        """
        Main entry of delta debugging.

        @param args args parsed by ArgumentParser, used to running debugged tool
        @param file_list the list of files that need to be minimized
        @param n the granularity of how to divide the file_list (i.e. divide file_list roughly even to n subsets)
        """
        # Base case check.
        if (len(file_list) == 1):
            return file_list if self.interesting(file_list) else list()

        delta_list = ListUtil.chunkify(file_list, n)

        for delta_chunk in delta_list:
            complement_chunk = ListUtil.get_complement_list(delta_chunk, file_list)

            if self.interesting(delta_chunk):
                # Reduce to subset delta_chunk.
                return self.minimize_file_set(delta_chunk, 2) if len(delta_chunk) > 1 else delta_chunk

            elif self.interesting(complement_chunk):
                # Reduce to complement of delta_chunk.
                return self.minimize_file_set(complement_chunk, max(n - 1, 2)) if len(delta_chunk) > 1 else complement_chunk

        if n < len(file_list):
            # Increase divide granularity on file_list.
            return self.minimize_file_set(file_list, min(len(file_list), 2 * n))
        else:
            # Done.
            return file_list if self.interesting(file_list) else list()

    def interesting(self, file_list):
        """
        The test function in delta debugging.

        Return true if the file_list is interesting, i.e. trigger a crash in the debugged tool.
        Return false otherwise.
        """
        exec_result = ToolRunningUtil.running_tool(self.tool_args, file_list, self.target_classpath, "file_set_minimization")

        # Delegate to InterestingJudger to decide if current test case is interesting.
        is_interesting = InterestingJudger.interesting(exec_result)
        print("Checked with files: {}. Is interesting: {}.".format(' '.join(file_list), is_interesting))
        return is_interesting

class ToolRunningUtil(object):
    """
    Util class for executing underlying tools and compilations.

    it provides APIs to outside of running tools, test if a given file is compilable, etc.
    """

    # TODO: decopuling with args
    @staticmethod
    def compilable(args, java_file, classpath):
        """
        Test if a given java_file is compilable.
        Return True if compilable, False otherwise.
        """
        compile_cmd = ['javac', '-classpath', classpath, java_file]
        compile_status = common.run_cmd(compile_cmd, args, None)
        return compile_status['return_code'] == 0

    @staticmethod
    def running_tool(args, file_list, target_classpath, log_file_path=None):
        """
        Runnning the debugged tool on given file_list.
        Return the tool execution return code.
        """
        tool_cmd = SUPPORT_TOOLS[args.debuggedTool].get_tool_command(args, target_classpath, file_list)
        execute_status = common.run_cmd(tool_cmd, args, log_file_path)
        return execute_status

class ListUtil(object):
    """
    Util class for list operations.
    """

    @staticmethod
    def chunkify(file_list, n):
        """
        Divide the given file_list into n chunks of approximately equal length.
        The order in original file_list would be kept.
        E.g. given list [0, 1, 2], n is 2
        the out put would be [[0, 1], [2]]
        """
        k, m = divmod(len(file_list), n)
        return [file_list[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] for i in range(n)]

    @staticmethod
    def get_complement_list(sub_list, domain_list):
        """
        Get the complement list of the given sub_list in domain_list.

        E.g. given chunk [2], domain_list[1, 2, 3], it returns [1, 3].
        """
        ###TODO: is the set() operation here would break the order in original list?
        return list(set(domain_list) - set(sub_list))
