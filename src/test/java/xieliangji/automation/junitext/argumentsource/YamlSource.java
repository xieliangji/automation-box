package xieliangji.automation.junitext.argumentsource;

import org.junit.jupiter.params.provider.ArgumentsSource;

import java.lang.annotation.*;

@Target({ ElementType.ANNOTATION_TYPE, ElementType.METHOD })
@Retention(RetentionPolicy.RUNTIME)
@Documented
@ArgumentsSource(YamlArgumentsProvider.class)
public @interface YamlSource {
    String filepath() default "";
}
