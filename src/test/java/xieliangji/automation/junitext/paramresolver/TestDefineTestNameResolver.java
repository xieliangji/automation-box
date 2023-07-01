package xieliangji.automation.junitext.paramresolver;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(DefineTestNameResolver.class)
public class TestDefineTestNameResolver {

    @Test
    @DisplayName("测试参数注入")
    public void inject(@DefineTestNameResolver.TestName String testName, TestInfo testInfo) {
        System.out.println(testName);
    }
}
