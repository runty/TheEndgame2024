/* Host test: decode the on-wire samples and check GRB order and V6 timing. */
#include <assert.h>
#include <stdio.h>
#include <endgame/ws2812_v6_encode.h>

static void check(uint8_t r, uint8_t g, uint8_t b) {
    uint8_t encoded[ENDGAME_PIXEL_BYTES], decoded[3] = {0};
    endgame_encode_pixel(encoded, r, g, b);
    for (unsigned bit = 0; bit < 24; ++bit) {
        unsigned high = 0;
        int fell = 0;
        for (unsigned sample = 0; sample < 20; ++sample) {
            unsigned at = bit * 20 + sample;
            int on = (encoded[at / 8] >> (7 - at % 8)) & 1;
            if (on) { assert(!fell); ++high; } else { fell = 1; }
        }
        unsigned high_ns_x2 = high * 125;
        unsigned low_ns_x2 = (20 - high) * 125;
        assert(low_ns_x2 >= 1160 && low_ns_x2 <= 2000);
        int one = high_ns_x2 >= 1160;
        assert(one ? high_ns_x2 <= 2000 :
               (high_ns_x2 >= 440 && high_ns_x2 <= 760));
        decoded[bit / 8] = (decoded[bit / 8] << 1) | one;
    }
    assert(decoded[0] == g && decoded[1] == r && decoded[2] == b);
    assert((encoded[ENDGAME_PIXEL_BYTES - 1] & 1) == 0);
}
int main(void) {
    for (unsigned value = 0; value < 256; ++value) {
        check(value, value ^ 0xa5, 255 - value);
    }
    check(0, 0, 0); check(255, 255, 255);
    puts("258 frames: GRB order, pulse timings, and final low level passed");
}
