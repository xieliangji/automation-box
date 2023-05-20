package xieliangji.automation.playwright.demo;

import com.microsoft.playwright.assertions.PlaywrightAssertions;
import org.junit.jupiter.api.*;
import xieliangji.automation.playwright.BeforeAfterActions;

@DisplayNameGeneration(DisplayNameGenerator.Standard.class)
public class GoogleNcrPageTest extends BeforeAfterActions {

    private GoogleNcrPage googleNcrPage;

    @BeforeEach
    public void initGoogleNcrPage() {
        googleNcrPage = new GoogleNcrPage(page);
    }

    @Test
    @DisplayName("测试google搜索首页标题")
    public void testGoogleNcrPageTitle() {
        String expectedPageTitle = "Google";
        googleNcrPage.navigate();

        PlaywrightAssertions.assertThat(page).hasTitle(expectedPageTitle);
    }

    @Test
    @DisplayName("测试搜索ChatGPT结果页标题")
    public void testChatGPTPhraseSearchPageTitle() {
        String phrase = "chatGPT";
        String expectedPageTitle = "%s - Google Search".formatted(phrase);
        googleNcrPage
                .navigate()
                .setSearchPhrase(phrase)
                .triggerSearchByEnter();

        PlaywrightAssertions.assertThat(page).hasTitle(expectedPageTitle);
    }
}
