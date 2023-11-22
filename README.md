# v2rayA-cli-client-light

<!-- [![PyPI - Version](https://img.shields.io/pypi/v/v2raya-cli-client.svg)](https://pypi.org/project/v2raya-cli-client) -->
<!-- [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/v2raya-cli-client.svg)](https://pypi.org/project/v2raya-cli-client) -->

-----

**Table of Contents**

- [v2rayA-cli-client-light](#v2raya-cli-client-light)
  - [Installation](#installation)
  - [Usage](#usage)
    - [定时](#定时)
  - [License](#license)

## Installation

```bash
pip install -e .
```

## Usage

```bash
v2ctl --help
# init with username and password
v2ctl account <username>
# login with username and password
v2ctl login <username>
v2ctl touch
v2ctl smart
```

### 定时

```bash
crontab -u $USER -e
# Example
0 */2 * * * export PATH=$PATH:/home/cromarmot/.local/bin; v2ctl smart --fast-server 1 >> /tmp/v2ctl.log
```

## License

`v2raya-cli-client` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
