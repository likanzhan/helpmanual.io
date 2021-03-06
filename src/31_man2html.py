import re
import subprocess
import sys
from pathlib import Path

from devtools import debug


def to_ansi(name):
    env = {
        'COLUMNS': '1000',
        'LINES': '100',
        'TERM': 'xterm-256color',
        'LANG': 'en_GB.UTF-8',
    }

    cmd = 'script', '-e', '-q', '-c', f'man -P ul {name}', '/dev/null'
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=2)
    body = p.stdout.replace(b'\r\n', b'\n').decode()
    Path('file.raw').write_text(body)
    # debug(body[:2000])
    return body


ansi_re = re.compile(r'\x1b\[(?:\d|;)*[a-zA-Z]')
heading = re.compile(r'^\x1b\[1m(.+)\x1b\[0m')
seven_spaces = re.compile(r'^ {7}')
three_spaces = re.compile(r'^ {3}')
start_space = re.compile(r'^ +')

regexes = [
    (re.compile(r'\x1b\[1m(.+?)\x1b\[0m'), r'<b>\1</b>'),
    (re.compile(r'\x1b\[4m(.+?)\x1b\[24m'), r'<u>\1</u>'),
    (re.compile(r'\x1b\[7m(.+?)\x1b\[0m'), r'<span class="bu">\1</span>'),
    (re.compile(r'</([bu])>( *)<\1>'), r'\2'),
]

html_escapes = {'&': '&amp;', '<': '&lt;', '>': '&gt;'}
template = """
<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title></title>
<style>
body {
  word-wrap: break-word;
  font-family: monospace;
  color: #AAAAAA;
  background-color: #000000;
}
.c {
  white-space: pre-wrap;
  margin-left: 3.5rem;
}
.dedent {
  margin-left: 3.5rem;
}
.inv_foreground { color: #000000; }
.inv_background { background-color: #AAAAAA; }
h3 {
  padding: 0;
  margin: 0;
  line-height: 1;
  font-size: 1.1rem;
}
h4 {
  padding: 0;
  margin: 0 0 1rem;
  line-height: 1;
  font-size: 1rem;
  font-weight: 700;
  margin-left: -2rem;
}
.table-line {
  color: #4fc3f7
}
.bu {
  font-weight: 700;
  text-decoration: underline;
}
{{styles}}
</style>
</head>
<body>
{{html}}
</body>
</html>
"""


def strip_ansi(value):
    return ansi_re.sub('', value)


def replace_ansi(ansi):
    for pattern, special in html_escapes.items():
        ansi = ansi.replace(pattern, special)
    for regex, rep in regexes:
        ansi = regex.sub(rep, ansi)
    return ansi


def ansi_to_html(ansi):
    lines = []

    def add_line(line_):
        line_ = replace_ansi(line_)

        # convert table borders to a funky colour, will this mess up with just pipe operators?
        line_ = re.sub('([┌┬┐└┴┘├┼┤─│]+)', r'<span class="table-line">\1</span>', line_)

        for indent in range(20, 0, -1):
            regex = re.compile('^ {%s}' % (7 + indent))
            if regex.search(line_):
                lines.append(f'<div class="indent-{indent}">{regex.sub("", line_)}</div>')
                return
        if seven_spaces.search(line_):
            # normal line
            lines.append(seven_spaces.sub('', line_ + '\n'))
        elif three_spaces.search(line_):
            lines.append(f'<h4>{three_spaces.sub("", line_)}</h4>')
        else:
            # line is weird and has non standard indent, could use and h4 here?
            lines.append(f'<div class="dedent">{line_}</div>')

    in_para = False
    in_section = False
    for line in ansi.split('\n')[1:-2]:
        if heading.search(line):
            if in_para:
                lines.append('</pre>\n')
                in_para = False
            if in_section:
                lines.append('</section>\n\n')
            h = heading.sub(r'\1', line)
            lines.append(f'<h3>{strip_ansi(h)}</h3>\n<section>\n')
            in_section = True
        elif line == '':
            if in_para:
                lines.append('</pre>\n')
                in_para = False
        else:
            if not in_para:
                lines.append('<pre class="c">')
                in_para = True
            add_line(line)

    if in_section:
        lines.append('</section>\n')
    html = ''.join(lines)

    m = ansi_re.search(html)
    if m:
        debug(html[m.start() - 100:m.end() + 100])
        raise RuntimeError('ansi strings found in html')
    html = template.replace('{{html}}', html)
    styles = '\n'.join(f'.indent-{v} {{margin-left: {v/2:0.1f}rem;}}' for v in range(1, 21))
    return html.replace('{{styles}}', styles)


def main(path: Path, save=False):
    command_name = path.name.split('.', 1)[0]
    ansi = to_ansi(command_name)
    html = ansi_to_html(ansi)
    if save:
        Path('file.html').write_text(html)


def run_all():
    count = 0
    for p in Path('/usr/share/man/man1').iterdir():
        try:
            main(p)
        except Exception as e:
            raise RuntimeError(f'error in {p}') from e
        else:
            count += 1
            print(count, p)
    print(f'processed {count} files')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        file_path = Path(sys.argv[1])
        main(file_path, save=True)
    else:
        run_all()
