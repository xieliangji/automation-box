package xieliangji.automation.junitext.mini;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.RepeatedTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.Objects;

public class TestBasis {

    private void printInvokerMethodName(Integer traceIndex) {
        if (Objects.isNull(traceIndex)) {
            traceIndex = 0;
        }
        StackTraceElement[] elements = new Exception().getStackTrace();
        if (elements.length <= traceIndex) {
            System.out.println(elements[0].getMethodName());
            return;
        }
        System.out.println(elements[traceIndex].getMethodName());
    }

    @Test
    public void printTrace() {
        printInvokerMethodName(1);
    }

    @ParameterizedTest
    @ValueSource(strings = {"hello", "world"})
    public void printTraceString(String arg) {
        printInvokerMethodName(1);
        System.out.println("arg: " + arg);
    }

    @Test
    @DisplayName("自定义测试名")
    public void customDisplayName() {
        printInvokerMethodName(1);
    }

    @AnnotationInherit.TagNormalTest
    public void annotationInherit() {
        printInvokerMethodName(1);
    }

    @RepeatedTest(value = 2, name = "模板测试{currentRepetition} of {totalRepetitions}") // repeat run 2 times
    public void repeated() {
        printInvokerMethodName(1);
    }

    @Test
    @Disabled
    public void disable() {
        printInvokerMethodName(1);
    }
}
