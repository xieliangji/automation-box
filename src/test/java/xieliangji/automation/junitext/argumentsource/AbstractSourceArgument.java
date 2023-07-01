package xieliangji.automation.junitext.argumentsource;

import com.google.gson.Gson;

public abstract class AbstractSourceArgument {

    public abstract String getTestName();

    public final String toString() {
        return getTestName();
    }

    public String jsonStr() {
        return new Gson().toJson(this);
    }
}
