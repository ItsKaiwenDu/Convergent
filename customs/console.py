class MockConsole:
    def print(self, *args, **kwargs):
        import re
        msg = " ".join(map(str, args))
        msg = re.sub(r"\[.*?\]", "", msg)
        if 'end' in kwargs:
            print(msg, end=kwargs['end'])
        else:
            print(msg)
            
    def rule(self, title):
        print(f"\n{'='*20} {title} {'='*20}")
