package xieliangji.automation.junitext.example;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

public class TestNamedArgumentTests {

    @DisplayName("测试外部参数生成提供器")
    @ParameterizedTest
    @MethodSource("xieliangji.automation.junitext.example.ExternalDataProvider#provideForTest1")
    public void test1(ExternalDataProvider.Test1Arg arg) {
        System.out.println(arg);
    }
}
