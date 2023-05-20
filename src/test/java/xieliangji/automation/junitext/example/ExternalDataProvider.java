package xieliangji.automation.junitext.example;

import org.junit.jupiter.params.provider.Arguments;
import xieliangji.automation.junitext.TestNamed;
import xieliangji.automation.junitext.TestNamedArgumentHelper;

import java.util.List;
import java.util.stream.Stream;

/**
 * JUnit - data provider can be internal or external
 *
 */
public class ExternalDataProvider {

    public static Stream<Arguments> provide() {
        List<TestDataSample> args = List.of(
                new TestDataSample("第3条测试用例", "参数1", true, 3),
                new TestDataSample("第4条测试用例", "参数1", true, 3)
        );
        return TestNamedArgumentHelper.generateArgumentsStream(args);
    }
}
