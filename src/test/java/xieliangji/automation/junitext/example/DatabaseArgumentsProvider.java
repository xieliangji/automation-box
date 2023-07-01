package xieliangji.automation.junitext.example;

import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.ArgumentsProvider;
import org.junit.jupiter.params.support.AnnotationConsumer;

import java.util.stream.Stream;

public class DatabaseArgumentsProvider implements ArgumentsProvider, AnnotationConsumer<DatabaseSource> {
    @Override
    public Stream<? extends Arguments> provideArguments(ExtensionContext context) throws Exception {
        // we can extend with reversing the data supply control in here
        // we use a specified @DisplayName to denote the test method
        // then we use the displayName to match our testdata for this test method
        // for example, we can connect a file or a database to fetch our whole testdata for the test methods
        // in our test data record, we have a property (eg . testName), the property value is match the displayName
        // then we can fetch the record and convert to the argument/parameter type entity
        // awesome
        System.out.println(context.getDisplayName());

        System.out.println(context.getTestMethod().orElseThrow(() -> new RuntimeException("no test method")).getName());
        return Stream.of(
                Arguments.of(new TestDisplayNames.TestData("测试用例1", "sam", 12)),
                Arguments.of(new TestDisplayNames.TestData("测试用例2", "alice", 20))
        );
    }

    @Override
    public void accept(DatabaseSource databaseSource) {

    }
}
