# JUnit5 定义的一些概念

- Platform定义的概念
    - Container - 容器: 在测试树中有子节点的节点，容器可以有子容器 eg. **Test Class**
    - Test - 测试: 在测试树中被执行时，会验证预期行为 eg. **`@Test` method**

- Jupiter 定义的概念
    - Lifecycle Method - 生命周期方法:
        - 被 `@BeforeAll` `@AfterAll` `@BeforeEach` `@AfterEach`标注的方法
    - Test Class - 测试类:
        - 包含至少一个测试方法的任何 **top-level** | **static member** | `@Nested` class
    - Test Method - 测试方法:
        - 被 `@Test` `@RepeatedTest` `@ParameterizedTest` `@TestFactory` `@TestTemplate` 标注的方法
        - 除了`@Test`, 其他注解都会在测试树中创建容器

测试框架的目的是用于管理及执行我们的测试用例，对于我们日常的测试用例我们的需求：
1. 执行: 独立执行、依赖执行
2. 管理: CRUD、分组、模板重用
3. 声明周期: 这个概念比较巧妙

框架具备管理测试用例、执行测试用例的能力，所以我们要挖掘
1）管理需求
2）执行需求
衍生出，我们在设计一个工具的时候，需要抽象出工具管理的对象及其状态。
管理对象需要进行状态流转(万物存在的意义在于运动)。
这也就意味着我们需要把对象的状态流转逻辑理清楚。
为了达成这些流转逻辑，我们需要提供哪些服务。

我们对处理对象的状态抽象整合越好，意味着我们的框架未来能够提供更好的服务的可能性越大

自动化服务的是测试用例，所以make the testcase could be automation

# How to make the testcases be automation?
# How to extend the automation?



# Save More and Use Faster