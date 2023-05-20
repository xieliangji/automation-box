package xieliangji.automation.junitext.example;

import org.junit.jupiter.params.provider.Arguments;
import xieliangji.automation.junitext.TestNamed;
import xieliangji.automation.junitext.TestNamedArgumentHelper;

import java.util.List;
import java.util.stream.Stream;

public class ExternalDataProvider {

    public static Stream<Arguments> provideForTest1() {
        List<Test1Arg> args = List.of(
                new Test1Arg("测试1", "参数1", 1),
                new Test1Arg("测试2", "参数2", 2)
        );
        return TestNamedArgumentHelper.generateArgumentsStream(args);
    }

    public static class Test1Arg implements TestNamed {

        private String testName;

        private String argName;

        private Integer argValue;

        public Test1Arg(String testName, String argName, Integer argValue) {
            this.testName = testName;
            this.argName = argName;
            this.argValue = argValue;
        }

        public void setTestName(String testName) {
            this.testName = testName;
        }

        public String getArgName() {
            return argName;
        }

        public void setArgName(String argName) {
            this.argName = argName;
        }

        public Integer getArgValue() {
            return argValue;
        }

        public void setArgValue(Integer argValue) {
            this.argValue = argValue;
        }

        @Override
        public String getTestName() {
            return testName;
        }

        @Override
        public String toString() {
            return "Test1Arg{" +
                    "testName='" + testName + '\'' +
                    ", argName='" + argName + '\'' +
                    ", argValue=" + argValue +
                    '}';
        }
    }
}
