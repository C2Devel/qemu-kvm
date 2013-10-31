#include "audio/audio.h"

#ifdef CONFIG_MIXEMU
# undef CONFIG_MIXEMU
# include "hda-audio.c"
#endif
