package xieliangji.automation.playwright.demo;

import com.microsoft.playwright.*;
import com.microsoft.playwright.assertions.PlaywrightAssertions;
import org.junit.jupiter.api.*;

/**
 * @see <a href="https://playwright.dev/java/docs/running-tests">Running tests</a>
 * @see <a href="https://playwright.dev/java/docs/test-runners">Test runners</a>
 */
public class TestOfficialRunning {

    static Playwright playwright;
    static Browser browser;
    BrowserContext context;
    Page page;

    @BeforeAll
    static void launchBrowser() {
        playwright = Playwright.create();
//        browser = playwright.chromium().launch(new BrowserType.LaunchOptions().setHeadless(false));
        browser = playwright.chromium().launch();
    }

    @AfterAll
    static void closeBrowser() {
        playwright.close();
    }

    @BeforeEach
    void createContextAndPage() {
        context = browser.newContext();
        page = context.newPage();
    }

    @AfterEach
    void closeContext() {
        context.close();
    }

    @Test
    void shouldCheckTheBox() {
        page.setContent("<input id='checkbox' type='checkbox'></input>");
        page.locator("input").check();

        Assertions.assertTrue((Boolean) page.evaluate("() => window['checkbox'].checked"));
    }

    @Test
    void shouldClickButton() {
        page.navigate(
                "data:text/html, <script>var result;</script><button onclick='result=\"Clicked\"'>Go</button>");
        page.locator("button").click();

        Assertions.assertEquals("Clicked", page.evaluate("result"));
    }

    @Test
    void shouldSearchWiki() {
        page.navigate("https://wikipedia.org/");
        page.locator("input[name=\"search\"]").click();
        page.locator("input[name=\"search\"]").fill("playwright");
        page.locator("input[name=\"search\"]").press("Enter");

        Assertions.assertEquals("https://en.wikipedia.org/wiki/Playwright", page.url());
    }
}
