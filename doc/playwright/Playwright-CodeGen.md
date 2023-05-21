# Using codegen for recording

- setup

```bash
# run command below in your project root directory
# cause it need the pom.xml
# the exec.args value, you can set the url what you want
mvn exec:java -e \
-D exec.mainClass=com.microsoft.playwright.CLI \
-D exec.args="codegen demo.playwright.dev/todomvc"
```

- recording

```text
with the 'recording' status, you can generate the script follow your operation on the page
```

- pick locator

```text
click the <Pick Locator> button, then you can get the locator of element on the page
```

So this codegen tool is awesome, right?

## Generate test while preserving authenticated state