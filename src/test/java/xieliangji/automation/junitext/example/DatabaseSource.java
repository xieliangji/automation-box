package xieliangji.automation.junitext.example;

import org.junit.jupiter.params.provider.ArgumentsSource;

import java.lang.annotation.*;
import java.util.List;

@Target({ ElementType.ANNOTATION_TYPE, ElementType.METHOD })
@Retention(RetentionPolicy.RUNTIME)
@Documented
@ArgumentsSource(DatabaseArgumentsProvider.class)
public @interface DatabaseSource {
}
