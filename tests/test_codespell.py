from kodespel import kodespel


class TestCodeChecker:
    def test_split_line(self):
        checker = kodespel.CodeChecker()

        tests = [
            (
                'match = pat.search(current_line, 0, pos)',
                ['match', 'pat', 'search', 'current', 'line', 'pos']
            ),
            (
                '_obj.doSomething(VALUE, FooBar + Blah_Foo)',
                ['obj', 'do', 'Something', 'VALUE', 'Foo', 'Bar', 'Blah', 'Foo']
            ),
            (
                'HTTPResponse getXMLElement',
                ['HTTP', 'Response', 'get', 'XML', 'Element']
            ),
            (
                "args.reps = float('+inf')",
                ['args', 'reps', 'float', 'inf']
            ),
            (
                "help='run /bin/sh -c CMD')",
                ['help', 'run', 'bin', 'sh', 'c', 'CMD']
            ),
            (
                "Mr. O'Reilly & Sons Ltd.",
                ['Mr', 'O\'Reilly', 'Sons', 'Ltd']
            ),
            (
                "// these aren't in the spec",
                ['these', 'aren\'t', 'in', 'the', 'spec']
            ),
        ]

        for (input, expect) in tests:
            assert checker.split_line(input) == expect
