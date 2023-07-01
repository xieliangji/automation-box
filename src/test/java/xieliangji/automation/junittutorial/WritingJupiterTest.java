package xieliangji.automation.junittutorial;


import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.util.function.BooleanSupplier;
import java.util.stream.Stream;

/**
 * @see org.junit.platform.engine.TestEngine
 * - Define the API for developing a test framework that runs on the JUnit Platform
 * @see org.junit.jupiter.engine.JupiterTestEngine
 * - Running Jupiter based tests on the JUnit Platform
 * <p/>
 * Jupiter supports annotations for configuring tests
 * Jupiter supports annotations for extending framework
 */
class WritingJupiterTest {

    @Test
    @DisplayName("Simple quickstart test")
    void quickstartTest() {
        Assertions.assertTrue(true);
    }

    @ParameterizedTest(name = "{0}")
    @ValueSource(strings = {"values", "for", "assigning", "to", "parameter"})
    @DisplayName("Simple quickstart parameterized test")
    void quickstartParameterizedTest(String parameter) {
        String description = "values for assigning to parameter";
        Assertions.assertTrue(() -> description.contains(parameter),
                "failure message: [%s] is not in the statement");
    }

    @RepeatedTest(value = 3, name = "{displayName} - {currentRepetition} of {totalRepetitions}")
    @DisplayName("Simple quickstart repeated test")
    void quickstartRepeatedTest() {
        Assertions.assertTrue(true);
    }

    @TestFactory
    @DisplayName("Not display")
    Stream<DynamicTest> quickstartDynamicTest() {
        return Stream.of(DynamicTest.dynamicTest("Simple quickstart dynamic test",
                () -> Assertions.assertTrue(true)));
    }

    /**
     * @see org.junit.jupiter.api.extension.TestTemplateInvocationContextProvider
     */
    @TestTemplate
    @DisplayName("Simple quickstart test template")
    void quickstartTestTemplate() {
        Assertions.assertTrue(true);
    }

    /**
     * @see TestMethodOrder
     */
    @Nested
    @TestClassOrder(ClassOrderer.Random.class)
    @DisplayName("Simple quickstart @Nested and @ClassTestOrder")
    @Tag("Nested tests")
    class NestedClassTest {

        @Nested
        @DisplayNameGeneration(DisplayNameGenerator.Standard.class)
        class NestedNestedClass2 {
            @Test
            void testClassOrderTest() {
                Assertions.assertTrue(true);
            }
        }

        @Nested
        @Disabled
        class NestedNestedClass1 {
            @Test
            void testClassOrderTest() {
                Assertions.assertTrue(true);
            }
        }
    }


    @BeforeAll
    static void quickstartBeforeAll() {
        System.out.println("this method execute only once before all the tests within this class");
    }

    @AfterAll
    static void quickstartAfterAll() {
        System.out.println("this method execute only once after all the tests withing this class");
    }

    @BeforeEach
    void quickstartBeforeEach() {
        System.out.println("this method execute before each test");
    }

    @AfterEach
    void quickstartAfterEach() {
        System.out.println("this method execute after each test");
    }
    @Target({ ElementType.METHOD })
    @Retention(RetentionPolicy.RUNTIME)
    @Tag("composed")
    @Test
    @interface QuickstartComposedJupiterAnnotation {}

    @QuickstartComposedJupiterAnnotation
    @DisplayName("Simple quickstart composed Jupiter meta-annotations")
    void quickstartComposedMeta() {
        Assertions.assertTrue(true);
    }
}
