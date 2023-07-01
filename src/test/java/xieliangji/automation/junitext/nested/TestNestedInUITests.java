package xieliangji.automation.junitext.nested;

import com.fasterxml.jackson.core.type.TypeReference;
import com.google.gson.Gson;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import xieliangji.automation.junitext.argumentsource.BeforeEachExtension;
import xieliangji.automation.junitext.argumentsource.Person;
import xieliangji.automation.junitext.argumentsource.YamlSource;

import java.util.Map;

/**
 * 在我们进行ui自动化时，这种情况出现是不足为奇的：
 * 页面A -> <某个操作> -> (跳转) -> 页面B
 * 页面A -> <某个操作> -> (跳转) -> 页面C
 * ...
 * 基于以上情况，我们使用{@link org.junit.jupiter.api.Nested}来组织各页面的测试用例，会让我们的测试用例在逻辑可读性上会更强
 * 同时也能降低代码量
 * 这里我们以Playwright进行自动化测试为例
 */
public class TestNestedInUITests {

    @ExtendWith({BeforeEachExtension.class})
    private String ext;

    @ParameterizedTest(name = "{0}")
    @YamlSource
    public void readYml(Person arg,  TestReporter reporter) {
        Gson gson = new Gson();
        System.out.println(arg.jsonStr());
        reporter.publishEntry((Map<String, String>) gson.fromJson(gson.toJson(arg), new TypeReference<Map<String, String>>(){}.getType()));
    }

//
//    private static Playwright playwright;
//    private static Browser browser;
//    private BrowserContext context;
//    private Page page;
//
//    @BeforeAll
//    static void setupNavigateToPageA() {
//        playwright = Playwright.create();
//        browser = playwright.chromium().launch(); // perhaps you will launch with some options ...
//    }
//
//    @BeforeEach
//
//    @Nested
//    class StartPageA {
//
//    }

    static int count = 0;

    private int countCopy = 0;

    @BeforeAll
    static void assignCount() {
        count++;
    }

    @BeforeEach
    public void assignCountCopy() {
        countCopy++;
    }

    @Nested
    class InspectCounts {

        @Test
        public void inspect1() {
            System.out.printf("count: %s, countCopy: %s", count, countCopy);
        }

        @Test
        public void inspect2() {
            System.out.printf("count: %s, countCopy: %s", count, countCopy);
        }
    }
}
