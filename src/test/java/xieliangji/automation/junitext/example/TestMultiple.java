package xieliangji.automation.junitext.example;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.api.parallel.Execution;
import org.junit.jupiter.api.parallel.ExecutionMode;

@TestInstance(TestInstance.Lifecycle.PER_METHOD)
@Execution(ExecutionMode.CONCURRENT)
public class TestMultiple {

    @Test
    public void test1() {
        System.out.println(Thread.currentThread().getId());
    }

    @Test
    public void test2() {
        System.out.println(Thread.currentThread().getId());
    }

    @Test
    public void test3() {
        System.out.println(Thread.currentThread().getId());
    }
}
