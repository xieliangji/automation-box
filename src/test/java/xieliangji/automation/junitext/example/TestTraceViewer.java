package xieliangji.automation.junitext.example;

import com.microsoft.playwright.*;
import org.junit.jupiter.api.*;

import java.nio.file.Paths;

public class TestTraceViewer {

    private static Playwright playwright;
    private static Browser browser;
    private BrowserContext context;
    private Page page;

    @BeforeAll
    static void setup() {
        playwright = Playwright.create();
        browser = playwright.chromium().launch();
    }

    @AfterAll
    static void teardown() {
        browser.close();
        playwright.close();
    }

    @BeforeEach
    public void createContextAndPageWithContextTracing() {
        context = browser.newContext();
        context.tracing().start(new Tracing.StartOptions()
                .setScreenshots(true)
                .setSnapshots(true)
                .setSources(true));
        page = context.newPage();
    }

    @AfterEach
    public void stopTracingAndReleaseResource() {
        // save tracing with a zip archive exported.
        context.tracing().stop(new Tracing.StopOptions().setPath(Paths.get("trace.zip")));
        page.close();
        context.close();
    }

    @Test
    public void tracingOfficialSite() {
        page.navigate("https://playwright.dev");
    }

}
