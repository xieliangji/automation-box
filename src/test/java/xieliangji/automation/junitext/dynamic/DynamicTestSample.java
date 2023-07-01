package xieliangji.automation.junitext.dynamic;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.DynamicTest.dynamicTest;

public class DynamicTestSample {

    static class Person {
        private String testName;
        private final String name;
        private final Integer age;

        public Person(String testName, String name, Integer age) {
            this.testName = testName;
            this.name = name;
            this.age = age;
        }

        public String getName() {
            return name;
        }

        public Integer getAge() {
            return age;
        }

        public String getTestName() {
            return testName;
        }
    }

    @TestFactory
    @DisplayName("动态测试")
    public Stream<DynamicTest> generate() {
        return Stream.of(
                new Person("动态测试用例1", "黎思静", 18),
                new Person("动态测试用例2", "谢良基", 29)
        ).map(person -> dynamicTest(person.getTestName(),
                () -> System.out.println(person.getName() + ", " + person.getAge())));
    }
}
