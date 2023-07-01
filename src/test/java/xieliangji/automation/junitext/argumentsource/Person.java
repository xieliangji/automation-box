package xieliangji.automation.junitext.argumentsource;

public class Person extends AbstractSourceArgument{

    private String testName;
    private String name;
    private Integer age;

    public Person() {}

    @Override
    public String getTestName() {
        return testName;
    }

    public void setTestName(String testName) {
        this.testName = testName;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public Integer getAge() {
        return age;
    }

    public void setAge(Integer age) {
        this.age = age;
    }
}
