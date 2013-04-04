#include "hyperv.h"

static bool hyperv_relaxed_timing;

void hyperv_enable_relaxed_timing(bool val)
{
    hyperv_relaxed_timing = val;
}

bool hyperv_relaxed_timing_enabled(void)
{
    return hyperv_relaxed_timing;
}

