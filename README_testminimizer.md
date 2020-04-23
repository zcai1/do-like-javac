##### About Delta Debugging

Here is the [slides](http://www.ist.tugraz.at/teaching/pub/Main/SoftwareMaintenance/SOMADeltaDebugging.pdf) I found in the internet
that I can understand for delta debugging. And also my file set minimization algorithm is developed based on this slides.

#### Usage of test minimizer

TestMinimizer is a tool that helps minimize a test case from a real
project, which exposes a bug in Checker Framework or Checker Framework
Inference. The minimized test case will expose the same bug as the
real project, but will only contain the minimal code necessary to
reproduce the bug.

There are 2 kinds of information you can provide to TestMinimizer, in
order to let it know what an interesting test case that exposes a
bug is:

- `expectOutputRegex`: the tool output is interesting if it matches
  this regex. Generally this is for locking the output to contain a
  specific stack trace from a CF/CFI crash, or locking it to contain a
  misreported error (false-positive).

- `expectReturnCode`: the return code for an interesting test
  case. The default value is 1, which means CF/CFI abnormally
  terminated when running on the given test case (in other words,
  CF/CFI crashed). You can use 0 to indicate that CF/CFI still
  normally exits when run on an interesting test case.

With these 2 kinds of information, TestMinimizer extracts a minimized
interesting file set from the target project and then reduces the size
of each individual file in that file set.


#### Tool dependencies

TestMinimizer requires `Lithium` installed as a pip package:

```bash
git clone https://github.com/MozillaSecurity/lithium.git
cd lithium
python setup.py install
```

Or install it via `pip install`:

```
pip2 install lithium-reducer --user
```

You need to manually install this dependency at the moment.


#### Running the tool:

```bash
do-like-javac/dljc -t testminimizer \
    --debuggedTool <'check' or 'inference'> \
    --checker <checkerFullyQualifiedName> \
    --expectOutputRegex "python regex" \
    --expectReturnCode <0 or 1> \
    -- <your project build cmd>
```

##### Regex note

The parameter `--expectOutputRegex` takes the given argument as a
Python regex. You need to escape special characters in your regex. For
example, if you want the tool output to contain the stack trace line:
`at package.class.thisMethod(class.java:58)`, you need to escape the
special characters `(` and `)`. That means, the expected regex would
be: `at package.class.thisMethod\(class.java:58\)`.


##### Demo example

I've created a [demo
project](https://github.com/opprop/DemoProject4TestMinimizer)
that demos the TestMinimizer. You can clone it and try to run the demo
script there to have a better sense of what TestMinimizer can do for
you.


