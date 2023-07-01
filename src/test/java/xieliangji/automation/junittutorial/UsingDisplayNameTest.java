package xieliangji.automation.junittutorial;

import org.junit.jupiter.api.*;

import java.lang.reflect.Method;

@DisplayName("display name on test class")
class UsingDisplayNameTest {

    @DisplayName("display name on test method")
    void test() {
        Assertions.assertTrue(true);
    }

    @Test
    void testWithCustomDisplayNameGenerator() {

    }

    @Nested
    @DisplayNameGeneration(UsingDisplayNameTest.CustomGenerator.class)
    class UsingCustomDisplayNameTestClass {
        @DisplayName("demo with assertj")
        @Test
        void testAssertj() {
            org.assertj.core.api.Assertions.assertThat("hello").matches(".*ll.*");
        }
    }

    static class CustomGenerator extends DisplayNameGenerator.Standard {
        @Override
        public String generateDisplayNameForMethod(Class<?> testClass, Method testMethod) {
            return testMethod.getName();
        }
    }
}
