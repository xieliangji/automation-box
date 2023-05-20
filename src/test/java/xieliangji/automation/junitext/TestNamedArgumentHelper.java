package xieliangji.automation.junitext;

import org.junit.jupiter.api.Named;
import org.junit.jupiter.params.provider.Arguments;

import java.util.Collection;
import java.util.stream.Stream;

public class TestNamedArgumentHelper {
    /**
     * generate {@link Stream<Arguments>} from {@link Collection<? extends TestNamed>}
     *
     * @param arguments - instance collection of {@link TestNamed}
     * @return {@link Stream<Arguments>}
     */
    public static Stream<Arguments> generateArgumentsStream(Collection<? extends TestNamed> arguments) {
        return arguments.stream().map(argument -> Arguments.of(Named.of(argument.getTestName(), argument)));
    }
}
