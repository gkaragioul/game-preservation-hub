#pragma once

#include <sys/stat.h>

#define _mkdir(path) mkdir((path), 0755)
