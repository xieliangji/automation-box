package xieliangji.automation.junitext.example;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import xieliangji.automation.junitext.TestNamedArgumentHelper;

import java.util.List;
import java.util.stream.Stream;

public class TestWithParameterizedTestExtension {

    @ParameterizedTest
    @MethodSource("internalDataProvide")
    @DisplayName("参数化")
    public void testWithInternalDataProvider(TestDataSample testDataSample) {
        System.out.println(testDataSample);
    }

    @ParameterizedTest
    @MethodSource("xieliangji.automation.junitext.example.ExternalDataProvider#provide")
    @DisplayName("参数化")
    public void testWithExternalDataProvider(TestDataSample testDataSample) {
        System.out.println(testDataSample);
    }

    static Stream<Arguments> internalDataProvide() {
        return TestNamedArgumentHelper.generateArgumentsStream(List.of(
                new TestDataSample("第一条测试用例", "参数1", true, 3),
                new TestDataSample("第二条测试用例", "参数2", false, 4)
        ));
    }
}
