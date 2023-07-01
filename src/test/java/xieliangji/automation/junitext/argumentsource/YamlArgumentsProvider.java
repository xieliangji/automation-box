package xieliangji.automation.junitext.argumentsource;

import com.fasterxml.jackson.dataformat.yaml.YAMLMapper;
import com.google.gson.Gson;
import org.junit.jupiter.api.extension.ExtensionContext;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.ArgumentsProvider;
import org.junit.jupiter.params.support.AnnotationConsumer;
import org.junit.platform.commons.util.StringUtils;

import java.io.File;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;

public class YamlArgumentsProvider implements ArgumentsProvider, AnnotationConsumer<YamlSource> {

    private String filepath;

    @Override
    public void accept(YamlSource yamlSource) {
        this.filepath = yamlSource.filepath();
    }

    @Override
    public Stream<? extends Arguments> provideArguments(ExtensionContext context) throws Exception {
        Method testMethod = context.getTestMethod().orElseThrow(() -> new NoSuchMethodError("no test method"));
        Optional<Class<?>> sourceArgument =
                Arrays.stream(testMethod.getParameterTypes())
                        .filter(type -> type.getSuperclass().equals(AbstractSourceArgument.class))
                        .findFirst();
        if (sourceArgument.isEmpty()) {
            return Stream.of();
        }

        filepath = StringUtils.isBlank(filepath) ? "%s.yml".formatted(testMethod.getName()) : filepath;

        Class<?> argumentClass = sourceArgument.get();
        Gson gson = new Gson();
        Object object = new YAMLMapper().readValue(new File(filepath), Object.class);
        if (!(object instanceof List<?>)) {
            throw new Exception(
                    "yml should store list of %s type entities".formatted(argumentClass.getName()));
        }
        return ((List<?>) object)
                .stream()
                .map(entity -> Arguments.of(gson.fromJson(gson.toJson(entity), argumentClass)));
    }
}
