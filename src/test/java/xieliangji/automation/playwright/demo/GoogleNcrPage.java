package xieliangji.automation.playwright.demo;

import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;

/**
 * No Pre-Page
 */
@SuppressWarnings("UnusedReturnValue")
public class GoogleNcrPage {

    private static final String URL = "https://google.com/ncr";

    private final Page page;

    public GoogleNcrPage(Page page) {
        this.page = page;
    }

    public GoogleNcrPage navigate() {

        page.navigate(URL);
        return this;
    }

    public Locator getLogoImage() {
        return page.getByAltText("Google");
    }

    public Locator getSearchBox() {
        return page.locator("[name=q]");
    }


    public GoogleNcrPage setSearchPhrase(String phrase) {
        getSearchBox().fill(phrase);
        return this;
    }

    public GoogleNcrPage triggerSearchByEnter() {
        getSearchBox().press("Enter");
        return this;
    }
}
