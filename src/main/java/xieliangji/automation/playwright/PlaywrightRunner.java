package xieliangji.automation.playwright;

import com.microsoft.playwright.*;
import com.microsoft.playwright.assertions.PlaywrightAssertions;

public class PlaywrightRunner {

    public static void main(String[] args) throws InterruptedException {
        try (Playwright playwright = Playwright.create();
             Browser browser = playwright.chromium().launch(new BrowserType.LaunchOptions().setHeadless(false));
             BrowserContext context = browser.newContext();
             Page page = context.newPage();
        ){
            page.navigate("https://google.com/ncr");
            PlaywrightAssertions.assertThat(page).hasTitle("Google");
            Thread.sleep(2000);
        }
    }
}
