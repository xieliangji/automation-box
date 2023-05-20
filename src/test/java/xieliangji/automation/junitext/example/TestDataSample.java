package xieliangji.automation.junitext.example;

import xieliangji.automation.junitext.TestNamed;

/**
 * sample test data for parameterized test.
 */
public class TestDataSample implements TestNamed {

    private String testName;

    private String arg1;

    private Boolean arg2;

    private Integer arg3;

    @Override
    public String getTestName() {
        return testName;
    }

    public TestDataSample(String testName, String arg1, Boolean arg2, Integer arg3) {
        this.testName = testName;
        this.arg1 = arg1;
        this.arg2 = arg2;
        this.arg3 = arg3;
    }

    public void setTestName(String testName) {
        this.testName = testName;
    }

    public String getArg1() {
        return arg1;
    }

    public void setArg1(String arg1) {
        this.arg1 = arg1;
    }

    public Boolean getArg2() {
        return arg2;
    }

    public void setArg2(Boolean arg2) {
        this.arg2 = arg2;
    }

    public Integer getArg3() {
        return arg3;
    }

    public void setArg3(Integer arg3) {
        this.arg3 = arg3;
    }

    @Override
    public String toString() {
        return "TestDataSample{" +
                "testName='" + testName + '\'' +
                ", arg1='" + arg1 + '\'' +
                ", arg2=" + arg2 +
                ", arg3=" + arg3 +
                '}';
    }
}
