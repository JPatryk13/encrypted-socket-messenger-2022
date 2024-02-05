class SomeClass:
    def some_function(self) -> None:
        # print(self.some_function.__name__)
        pass

if __name__ == "__main__":
    SomeClass.some_function.has_been_called = False
    sc = SomeClass()
    sc.some_function()
    print(SomeClass.some_function.__name__)
    print(sc.some_function.__name__)
