package xieliangji.automation.junitext.mini;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

public class AnnotationInherit {

    @Retention(RetentionPolicy.RUNTIME)
    @Target(ElementType.METHOD)
    @Test
    @Tag("normal")
    @DisplayName("正常测试用例")
    public static @interface TagNormalTest {}
}
