"""nose unittest.TestCase subclasses. It is not necessary to subclass these
classes when writing tests; they are used internally by nose.loader.TestLoader
to create test cases from test functions and methods in test classes."""
import logging
import sys
import unittest
from inspect import isfunction
from nose.config import Config
from nose.util import resolve_name, test_address, try_run
import collections

log = logging.getLogger(__name__)
__all__ = ['Test']


class Test(unittest.TestCase):
    """The universal test case wrapper.
    When a plugin sees a test, it will always see an instance of this
    class. To access the actual test case that will be run, access the
    test property of the nose.case.Test instance."""
    __test__ = False  # do not collect

    def __init__(self, test, config=None, resultProxy=None):
        if not isinstance(test, collections.Callable):
            raise TypeError(
                "nose.case.Test called with argument %r that "
                "is not callable. A callable is required."
                % test
            )
        self.test = test
        if config is None:
            config = Config()
        self.config = config
        self.tbinfo = None
        self.capturedOutput = None
        self.resultProxy = resultProxy
        self.plugins = config.plugins
        self.passed = None
        unittest.TestCase.__init__(self)

    def __call__(self, *arg, **kwarg):
        return self.run(*arg, **kwarg)

    def __str__(self):
        name = self.plugins.testName(self)
        if name is not None:
            return name
        return str(self.test)

    def __repr__(self):
        return "Test(%r)" % self.test

    def afterTest(self, result):
        """Called after test is complete (after result.stopTest)"""
        try:
            afterTest = result.afterTest
        except AttributeError:
            pass
        else:
            afterTest(self.test)

    def beforeTest(self, result):
        """Called before test is run (before result.startTest)"""
        try:
            beforeTest = result.beforeTest
        except AttributeError:
            pass
        else:
            beforeTest(self.test)

    def exc_info(self):
        exc, exv, tb = sys.exc_info()
        return (exc, exv, tb)

    def id(self):
        return self.test.id()

    def address(self):
        """Return a round-trip name for this test, a name that can be
        fed back as input to loadTestByName and (assuming the same
        plugin configuration) result in the loading of this test."""
        if hasattr(self.test, 'address'):
            return self.test.address()
        else:
            return test_address(self.test)

    def _context(self):
        try:
            return self.test.context
        except AttributeError:
            pass
        try:
            return self.test.__class__
        except AttributeError:
            pass
        try:
            return resolve_name(self.test.__module__)
        except AttributeError:
            pass
        return None
    context = property(
        _context, None, None, "Get the context object of this test (if any)."
    )

    def run(self, result):
        """Modified run for the test wrapper.
        The wrapper calls addError/addFailure if own setup or teardown fails.
        Two additional methods are called: beforeTest and afterTest."""
        if self.resultProxy:
            result = self.resultProxy(result, self)
        try:
            try:
                self.beforeTest(result)
                self.runTest(result)
            except KeyboardInterrupt:
                raise
            except Exception:
                err = sys.exc_info()
                result.addError(self, err)
        finally:
            self.afterTest(result)

    def runTest(self, result):
        """Run the test. Plugins may alter the test by returning a
        value from prepareTestCase. The value must be callable and
        must accept one argument, the result instance."""
        test = self.test
        plug_test = self.config.plugins.prepareTestCase(self)
        if plug_test is not None:
            test = plug_test
        test(result)

    def shortDescription(self):
        desc = self.plugins.describeTest(self)
        if desc is not None:
            return desc
        test = self.test
        try:
            test._testMethodDoc = test._testMethodDoc.strip()
        except AttributeError:
            try:
                test._TestCase__testMethodDoc = \
                    test._TestCase__testMethodDoc.strip()
            except AttributeError:
                pass
        try:
            desc = self.test.shortDescription()
        except Exception:
            pass
        try:
            if desc == str(self.test):
                return
        except Exception:
            pass
        return desc


class TestBase(unittest.TestCase):
    """Common functionality for FunctionTestCase and MethodTestCase."""
    __test__ = False  # do not collect

    def id(self):
        return str(self)

    def runTest(self):
        self.test(*self.arg)

    def shortDescription(self):
        if hasattr(self.test, 'description'):
            return self.test.description
        func, arg = self._descriptors()
        doc = getattr(func, '__doc__', None)
        if not doc:
            doc = str(self)
        return doc.strip().split("\n")[0].strip()


class FunctionTestCase(TestBase):
    """TestCase wrapper for test functions.
    Don't use this class directly; it is used internally in nose to
    create test cases for test functions."""
    __test__ = False  # do not collect

    def __init__(self, test, setUp=None, tearDown=None, arg=tuple(),
                 descriptor=None):
        """Initialize the MethodTestCase.
        Required argument:
        * test -- the test function to call.
        Optional arguments:
        * setUp -- function to run at setup.
        * tearDown -- function to run at teardown.
        * arg -- arguments to pass to the test function. This is to support
          generator functions that yield arguments.
        * descriptor -- the function, other than the test, that should be used
          to construct the test name. This supports generator functions."""
        self.test = test
        self.setUpFunc = setUp
        self.tearDownFunc = tearDown
        self.arg = arg
        self.descriptor = descriptor
        TestBase.__init__(self)

    def address(self):
        """Return a round-trip name for this test, a name that can be
        fed back as input to loadTestByName and (assuming the same
        plugin configuration) result in the loading of this test."""
        if self.descriptor is not None:
            return test_address(self.descriptor)
        else:
            return test_address(self.test)

    def _context(self):
        return resolve_name(self.test.__module__)
    context = property(
        _context, None, None, """Get context (module) of this test"""
    )

    def setUp(self):
        """Run any setup function attached to the test function"""
        if self.setUpFunc:
            self.setUpFunc()
        else:
            names = ('setup', 'setUp', 'setUpFunc')
            try_run(self.test, names)

    def tearDown(self):
        """Run any teardown function attached to the test function"""
        if self.tearDownFunc:
            self.tearDownFunc()
        else:
            names = ('teardown', 'tearDown', 'tearDownFunc')
            try_run(self.test, names)

    def __str__(self):
        func, arg = self._descriptors()
        if hasattr(func, 'compat_func_name'):
            name = func.compat_func_name
        else:
            name = func.__name__
        name = "%s.%s" % (func.__module__, name)
        if arg:
            name = "%s%s" % (name, arg)
        return name
    __repr__ = __str__

    def _descriptors(self):
        """Get the descriptors of the test function: the function and
        arguments that will be used to construct the test name. In
        most cases, this is the function itself and no arguments. For
        tests generated by generator functions, the original
        (generator) function and args passed to the generated function
        are returned."""
        if self.descriptor:
            return self.descriptor, self.arg
        else:
            return self.test, self.arg


class MethodTestCase(TestBase):
    """Test case wrapper for test methods.
    Don't use this class directly; it is used internally in nose to
    create test cases for test methods."""
    __test__ = False  # do not collect

    def __init__(self, method, test=None, arg=tuple(), descriptor=None):
        """Initialize the MethodTestCase.
        Required argument:
        * method -- the method to call, may be bound or unbound. In either
          case, a new instance of the method's class will be instantiated to
          make the call.  Note: In Python 3.x, if using an unbound method, you
          must wrap it using pyversion.unbound_method.
        Optional arguments:
        * test -- the test function to call. If this is passed, it will be
          called instead of getting a new bound method of the same name as the
          desired method from the test instance. This is to support generator
          methods that yield inline functions.
        * arg -- arguments to pass to the test function. This is to support
          generator methods that yield arguments.
        * descriptor -- the function, other than the test, that should be used
          to construct the test name. This is to support generator methods."""
        self.method = method
        self.test = test
        self.arg = arg
        self.descriptor = descriptor
        if isfunction(method):
            raise ValueError(
                "Unbound methods must be wrapped using "
                "pyversion.unbound_method before passing to MethodTestCase"
            )
        self.cls = method.__self__.__class__
        self.inst = self.cls()
        if self.test is None:
            method_name = self.method.__name__
            self.test = getattr(self.inst, method_name)
        TestBase.__init__(self)

    def __str__(self):
        func, arg = self._descriptors()
        if hasattr(func, 'compat_func_name'):
            name = func.compat_func_name
        else:
            name = func.__name__
        name = "%s.%s.%s" % (self.cls.__module__, self.cls.__name__, name)
        if arg:
            name = "%s%s" % (name, arg)
        return name
    __repr__ = __str__

    def address(self):
        """Return a round-trip name for this test, a name that can be
        fed back as input to loadTestByName and (assuming the same
        plugin configuration) result in the loading of this test."""
        if self.descriptor is not None:
            return test_address(self.descriptor)
        else:
            return test_address(self.method)

    def _context(self):
        return self.cls
    context = property(
        _context, None, None, """Get context (class) of this test"""
    )

    def setUp(self):
        try_run(self.inst, ('setup', 'setUp'))

    def tearDown(self):
        try_run(self.inst, ('teardown', 'tearDown'))

    def _descriptors(self):
        """Get the descriptors of the test method: the method and
        arguments that will be used to construct the test name. In
        most cases, this is the method itself and no arguments. For
        tests generated by generator methods, the original
        (generator) method and args passed to the generated method
        or function are returned."""
        if self.descriptor:
            return self.descriptor, self.arg
        else:
            return self.method, self.arg
