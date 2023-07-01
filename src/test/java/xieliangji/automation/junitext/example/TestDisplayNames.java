package xieliangji.automation.junitext.example;

import com.google.gson.Gson;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.List;
import java.util.stream.Stream;

public class TestDisplayNames {

    @ParameterizedTest(name = "{0}")
    @DatabaseSource
    @DisplayName("测试用例名参数化")
    public void testDisplayName(TestData testData) {
        System.out.println(testData.toJson());
    }

    static Stream<Arguments> provideDisplayName() {
        return Stream.of(
                new TestData("测试用例1","sam", 12),
                new TestData("测试用例2","alice", 18)
        ).map(Arguments::of);
    }

    static class TestData {
        private String testName;
        private String name;
        private Integer age;

        public TestData(String testName, String name, Integer age) {
            this.testName = testName;
            this.name = name;
            this.age = age;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public Integer getAge() {
            return age;
        }

        public void setAge(Integer age) {
            this.age = age;
        }

        public String getTestName() {
            return testName;
        }

        public void setTestName(String testName) {
            this.testName = testName;
        }

        public String toString() {
            return testName;
        }

        public String toJson() {
            return new Gson().toJson(this);
        }
    }
}
