package xieliangji.automation.junittutorial;

import org.junit.jupiter.api.*;

/**
 * <a href="https://junit.org/junit5/docs/current/user-guide/#writing-tests-definitions">JUnit Definitions</a>
 * <ul>
 *     Platform
 *     <li>Container</li>
 *     <li>Test</li>
 * </ul>
 * <ul>
 *     Jupiter
 *     <li>Lifecycle Method</li>
 *     <li>Test Class</li>
 *     <li>Test Method</li>
 * </ul>
 */
@SuppressWarnings("NewClassNamingConvention")
class Definitions {

    @BeforeAll
    @AfterAll
    static void classLifecycleMethod() {
        System.out.println("execute once before/after all test methods");
    }

    @BeforeEach
    @AfterEach
    void instanceLifecycleMethod() {
        System.out.println("execute before/after each test method");
    }

    @Test
    void testMethodThatIndicateTestClass() {
        System.out.println("class contains test method, call test class");
    }

    @Nested
    class NestedTestClass {

        @Test
        void nestedTestClassTestMethod() {
            System.out.println("this is a test method of nested test class");
        }
    }
}
