#pragma once
#include_next <math.h>
#ifdef __cplusplus
extern "C" {
#endif
float sam_ref_tanhf(float value);
#ifdef __cplusplus
}
#endif
#define tanhf sam_ref_tanhf
