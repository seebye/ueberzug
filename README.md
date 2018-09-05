# Überzug

Überzug is a command line util
which allows to draw images on terminals by using child windows.

Advantages to w3mimgdisplay:
- no race conditions as a new window is created to display images
- expose events will be processed,  
  so images will be redrawn on switch workspaces
- tmux support
- terminals without the WINDOWID environment variable are supported
- chars are used as position - and size unit
- no memory leak (/ unlimited cache)

## Overview

- [Installation](#installation)
- [Communication](#communication)  
  * [Command formats](#command-formats)
  * [Actions](#actions)
    + [Add](#add)
    + [Remove](#remove)
- [Examples](#examples)

## Installation

```
$ sudo pip3 install ueberzug
```

## Communication

The communication is realised via stdin.  
A command is a request to execute a specific action with the passed arguments.  
(Therefore a command has to contain a key value pair "action": action_name)  
Commands are separated with a line break.

### Command formats

- json: Command as json object
- simple: Key-value pairs seperated by a tab,  
          pairs are also seperated by a tab  
- bash: dump of an associative array (`declare -p variable_name`)

### Actions

#### Add

Name: add  
Description:  
Adds an image to the screen.  
If there's already an image with the same identifier  
it will be replaced.

| Key           | Type         | Description                                                        | Optional |
|---------------|--------------|--------------------------------------------------------------------|----------|
| identifier    | String       | a freely choosen identifier of the image                           | No       |
| x             | Integer      | x position                                                         | No       |
| y             | Integer      | y position                                                         | No       |
| path          | String       | path to the image                                                  | No       |
| width         | Integer      | desired width; original width will be used if not set              | Yes      |
| height        | Integer      | desired height; original width will be used if not set             | Yes      |
| max_width     | Integer      | image will be resized (while keeping it's aspect ratio) if it's width is bigger than max width | Yes |
| max_height    | Integer      | image will be resized (while keeping it's aspect ratio) if it's height is bigger than max height | Yes |
| draw          | Boolean      | redraw window after adding the image, default True                 | Yes      |

#### Remove

Name: remove  
Description:  
Removes an image from the screen.  

| Key           | Type         | Description                                                        | Optional |
|---------------|--------------|--------------------------------------------------------------------|----------|
| identifier    | String       | a previously used identifier                                       | No       |
| draw          | Boolean      | redraw window after removing the image, default True               | Yes      |


## Examples

Command formats:

- Json add command: `{"action": "add", "x": 0, "y": 0, "path": "/some/path/some_image.jpg"}`  
- Simple add command: `action add x   0   y   0   path    /some/path/some_image.jpg`  
- Bash add command: `declare -A command=([path]="/some/path/some_image.jpg" [action]="add" [x]="0" [y]="0" )`  

Bash library:

```bash
source "`ueberzug library`"

ImageLayer -< <(
    ImageLayer::add [identifier]="example0" [x]="0" [y]="0" [path]="/some/path/some_image0.jpg"
    ImageLayer::add [identifier]="example1" [x]="0" [y]="0" [path]="/some/path/some_image1.jpg"
    read
    ImageLayer::remove [identifier]="example0"
    read
)
```

Scripts:

- Mastodon viewer: https://github.com/seebye/ueberzug/blob/master/examples/mastodon.sh
