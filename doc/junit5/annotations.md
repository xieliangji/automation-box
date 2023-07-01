# Annotations
for **Configuring** tests and **Extending** the framework
<br/>
located in the `org.junit.jupiter.api package` commonly

- annotations
  - `@Test`
  - `@ParameterizedTest`
  - `@RepeatedTest` - denotes method as a test template
  - `@TestFactory` - denotes method as a _**test factory**_ for **dynamic tests**
  - `@TestTemplate`
  - `@TestClassOrder`
  - `@TestMethodOrder`
  - `@TestInstance` - configure _**test instance lifecycle**_
  - `@DisplayName`
  - `@DisplayNameGeneration`
  - `@BeforeEach/@AfterEach`
  - `@BeforeAll/@AfterAll`
  - `@Nested` - denotes the annotated class is a non-static _**nested test class**_
  - `@Tag` - for filtering tests
  - `@Disable`
  - `@Timeout`
  - `@ExtendWith` - register extensions declaratively
  - `@RegisterExtension` - register extensions programmatically
  - `@TempDir` - supply a _**temporary directory**_ via field/parameter injection in **lifecycle/test** method

- meta-annotations
```java
// eg. @Fast = @Tag("fast")
@Tag("fast")
public @interface Fast {}

// eg. @FastTest = @Test + @Tag("fast")
@Test
@Tag("fast")
public @interface FastTest {}

@FastTest
public void someTest() {}
@Fast
public void someTest1() {}

```