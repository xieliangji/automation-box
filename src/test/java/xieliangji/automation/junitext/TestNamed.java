package xieliangji.automation.junitext;

/**
 * argument of JUnit5 test method that holds 'testName' field.
 */
public interface TestNamed {

    /**
     * supply test name from the parameterized test parameter <test data>.
     * @return - the test name
     */
    String getTestName();
}
