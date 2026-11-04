/*
 * hexharness: runs a compiled ATmega328P ELF on simavr and records what it does.
 *
 * usage: hexharness --elf fw.elf --scenario scenario.json --out result.json
 *                   [--wall-limit-ms N] [--no-sim-cap]
 *
 * Inputs are injected on a fixed simulated-time tick, so every run is
 * reproducible from the scenario seed. The result JSON is written only at the
 * end of a run, which is why an external SIGKILL produces no output at all.
 */
#include <errno.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <cjson/cJSON.h>

#include <simavr/avr_adc.h>
#include <simavr/avr_ioport.h>
#include <simavr/avr_uart.h>
#include <simavr/sim_avr.h>
#include <simavr/sim_elf.h>
#include <simavr/sim_irq.h>
#include <simavr/sim_time.h>

#define F_CPU_HZ 16000000UL
#define VCC_MV 5000
#define MAX_SIM_MS 30000.0
#define DEFAULT_SIM_MS 10000.0
#define DEFAULT_WALL_LIMIT_MS 27000
#define TICK_US 100
#define ANALOG_EVERY_TICKS 10 /* analog inputs refresh once per simulated ms */
#define TRACE_STEP_MS 10.0
#define NUM_PINS 20 /* D0-D13 then A0-A5 */
#define MAX_PIN_EVENTS 50000
#define MAX_PWM_EVENTS 20000
#define MAX_SERIAL_LINES 20000
#define MAX_LINE_BYTES 512
#define MAX_TRACE_POINTS 20000

typedef struct
{
    double t_ms;
    double mv;
} point_t;

typedef struct
{
    double t_ms;
    double width_ms;
    double mv;
} spike_t;

typedef struct
{
    double t_ms;
    int value;
} dig_event_t;

typedef struct
{
    double from_ms;
    double to_ms;
} float_window_t;

typedef struct
{
    int has_analog;
    point_t *points;
    int n_points;
    spike_t *spikes;
    int n_spikes;
    double noise_mv;

    int has_digital;
    int initial;
    dig_event_t *events;
    int n_events;
    int next_event;

    float_window_t *floats;
    int n_floats;
    double float_mv; /* random-walk state while floating */
    double float_next_flip_ms;
    int float_level;

    double last_mv;
    double bucket_min;
    double bucket_max;
    int bucket_used;

    int driven_level; /* -1 until the harness has driven this pin */
} pin_input_t;

typedef struct
{
    double t_ms;
    int pin;
    int value;
    int is_output;
} pin_event_t;

typedef struct
{
    double t_ms;
    int pin;
    int duty;
} pwm_event_t;

typedef struct
{
    double t_ms;
    char *text;
} serial_line_t;

typedef struct
{
    double t_ms;
    int pin;
    double mv;
    double min_mv;
    double max_mv;
} trace_point_t;

typedef struct
{
    int pin;
    uint8_t port;
    uint8_t bit;
} pin_ctx_t;

typedef struct
{
    int pin;
    uint16_t tccr_addr;
    uint8_t com_bit;
    uint16_t ocr_addr;
} pwm_channel_t;

/* ATmega328P timer registers behind each analogWrite-capable Uno pin. */
static const pwm_channel_t PWM_CHANNELS[] = {
    {6, 0x44, 7, 0x47},  /* OC0A */
    {5, 0x44, 5, 0x48},  /* OC0B */
    {9, 0x80, 7, 0x88},  /* OC1A */
    {10, 0x80, 5, 0x8A}, /* OC1B */
    {11, 0xB0, 7, 0xB3}, /* OC2A */
    {3, 0xB0, 5, 0xB4},  /* OC2B */
};

static avr_t *g_avr;
static uint64_t g_rng;
static pin_input_t g_inputs[NUM_PINS];
static int g_last_level[NUM_PINS];
static pin_ctx_t g_pin_ctx[NUM_PINS];
static avr_irq_t *g_pin_irq[NUM_PINS];
static avr_irq_t *g_adc_irq[6];

static pin_event_t *g_pin_events;
static int g_n_pin_events;
static int g_pin_events_truncated;

static pwm_event_t *g_pwm_events;
static int g_n_pwm_events;
static int g_last_pwm[NUM_PINS];

static serial_line_t *g_lines;
static int g_n_lines;
static int g_lines_truncated;
static char g_line_buf[MAX_LINE_BYTES + 1];
static int g_line_len;
static double g_line_t_ms;

static trace_point_t *g_trace;
static int g_n_trace;
static double g_next_trace_ms;
static uint32_t g_tick_count;

static volatile sig_atomic_t g_term_requested;

/* Arduino Uno pin numbering: D0-D7 = PD0-7, D8-D13 = PB0-5, A0-A5 = PC0-5. */
static void pin_to_port(int pin, uint8_t *port, uint8_t *bit)
{
    if (pin < 8)
    {
        *port = 'D';
        *bit = (uint8_t)pin;
    }
    else if (pin < 14)
    {
        *port = 'B';
        *bit = (uint8_t)(pin - 8);
    }
    else
    {
        *port = 'C';
        *bit = (uint8_t)(pin - 14);
    }
}

static void pin_name(int pin, char *out, size_t n)
{
    if (pin < 14)
    {
        snprintf(out, n, "D%d", pin);
    }
    else
    {
        snprintf(out, n, "A%d", pin - 14);
    }
}

static int parse_pin(const char *s)
{
    int v;

    if (s == NULL || s[0] == '\0')
    {
        return -1;
    }
    v = atoi(s + 1);
    if ((s[0] == 'D' || s[0] == 'd') && v >= 0 && v <= 13)
    {
        return v;
    }
    if ((s[0] == 'A' || s[0] == 'a') && v >= 0 && v <= 5)
    {
        return 14 + v;
    }
    return -1;
}

static double now_ms_sim(void)
{
    return (double)g_avr->cycle * 1000.0 / (double)g_avr->frequency;
}

static double wall_ms(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

static uint64_t rng_next(void)
{
    /* xorshift64*: small, and identical across arm64 and amd64 */
    uint64_t x = g_rng;

    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    g_rng = x;
    return x * 0x2545F4914F6CDD1DULL;
}

static double rng_uniform(void)
{
    return (double)(rng_next() >> 11) / 9007199254740992.0;
}

static double rng_gauss(void)
{
    double u1 = rng_uniform();
    double u2 = rng_uniform();

    if (u1 < 1e-12)
    {
        u1 = 1e-12;
    }
    return sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
}

static int port_ddr_addr(uint8_t port)
{
    /* ATmega328P data-space addresses */
    return port == 'B' ? 0x24 : (port == 'C' ? 0x27 : 0x2A);
}

static int port_port_addr(uint8_t port)
{
    return port == 'B' ? 0x25 : (port == 'C' ? 0x28 : 0x2B);
}

static int pin_is_output(int pin)
{
    const pin_ctx_t *c = &g_pin_ctx[pin];

    return (g_avr->data[port_ddr_addr(c->port)] >> c->bit) & 1;
}

static int pin_pullup_on(int pin)
{
    const pin_ctx_t *c = &g_pin_ctx[pin];

    return (g_avr->data[port_port_addr(c->port)] >> c->bit) & 1;
}

static void on_pin_change(struct avr_irq_t *irq, uint32_t value, void *param)
{
    pin_ctx_t *c = (pin_ctx_t *)param;
    int level = value ? 1 : 0;

    (void)irq;
    if (g_last_level[c->pin] == level)
    {
        return;
    }
    g_last_level[c->pin] = level;
    if (g_n_pin_events >= MAX_PIN_EVENTS)
    {
        g_pin_events_truncated = 1;
        return;
    }
    g_pin_events[g_n_pin_events].t_ms = now_ms_sim();
    g_pin_events[g_n_pin_events].pin = c->pin;
    g_pin_events[g_n_pin_events].value = level;
    g_pin_events[g_n_pin_events].is_output = pin_is_output(c->pin);
    g_n_pin_events++;
}

/*
 * analogWrite does not move the GPIO in simavr, so read the timer registers.
 * duty is -1 when the compare output is disconnected and the pin is plain GPIO.
 */
static void poll_pwm(void)
{
    size_t i;

    for (i = 0; i < sizeof(PWM_CHANNELS) / sizeof(PWM_CHANNELS[0]); i++)
    {
        const pwm_channel_t *ch = &PWM_CHANNELS[i];
        int connected = (g_avr->data[ch->tccr_addr] >> ch->com_bit) & 1;
        int duty = connected ? (int)g_avr->data[ch->ocr_addr] : -1;

        if (duty == g_last_pwm[ch->pin])
        {
            continue;
        }
        g_last_pwm[ch->pin] = duty;
        if (g_n_pwm_events >= MAX_PWM_EVENTS)
        {
            continue;
        }
        g_pwm_events[g_n_pwm_events].t_ms = now_ms_sim();
        g_pwm_events[g_n_pwm_events].pin = ch->pin;
        g_pwm_events[g_n_pwm_events].duty = duty;
        g_n_pwm_events++;
    }
}

static void flush_serial_line(void)
{
    if (g_line_len == 0)
    {
        return;
    }
    if (g_n_lines >= MAX_SERIAL_LINES)
    {
        g_lines_truncated = 1;
        g_line_len = 0;
        return;
    }
    g_line_buf[g_line_len] = '\0';
    g_lines[g_n_lines].t_ms = g_line_t_ms;
    g_lines[g_n_lines].text = strdup(g_line_buf);
    g_n_lines++;
    g_line_len = 0;
}

static void on_uart_byte(struct avr_irq_t *irq, uint32_t value, void *param)
{
    char ch = (char)(value & 0xFF);

    (void)irq;
    (void)param;
    if (ch == '\r')
    {
        return;
    }
    if (ch == '\n')
    {
        g_line_t_ms = now_ms_sim();
        flush_serial_line();
        return;
    }
    if (g_line_len < MAX_LINE_BYTES)
    {
        g_line_t_ms = now_ms_sim();
        g_line_buf[g_line_len++] = ch;
    }
}

static int in_float_window(const pin_input_t *in, double t)
{
    int i;

    for (i = 0; i < in->n_floats; i++)
    {
        if (t >= in->floats[i].from_ms && t < in->floats[i].to_ms)
        {
            return 1;
        }
    }
    return 0;
}

static double analog_value_mv(pin_input_t *in, double t)
{
    double v = 0.0;
    int i;

    if (in_float_window(in, t))
    {
        /* A floating ADC input wanders and also picks up pin-to-pin noise. */
        in->float_mv += rng_gauss() * 60.0;
        if (in->float_mv < 0.0)
        {
            in->float_mv = -in->float_mv;
        }
        if (in->float_mv > VCC_MV)
        {
            in->float_mv = 2.0 * VCC_MV - in->float_mv;
        }
        v = in->float_mv + rng_gauss() * 120.0;
    }
    else
    {
        if (in->n_points > 0)
        {
            if (t <= in->points[0].t_ms)
            {
                v = in->points[0].mv;
            }
            else if (t >= in->points[in->n_points - 1].t_ms)
            {
                v = in->points[in->n_points - 1].mv;
            }
            else
            {
                for (i = 0; i + 1 < in->n_points; i++)
                {
                    if (t >= in->points[i].t_ms && t < in->points[i + 1].t_ms)
                    {
                        double span = in->points[i + 1].t_ms - in->points[i].t_ms;
                        double frac = span > 0.0 ? (t - in->points[i].t_ms) / span : 0.0;

                        v = in->points[i].mv + frac * (in->points[i + 1].mv - in->points[i].mv);
                        break;
                    }
                }
            }
        }
        if (in->noise_mv > 0.0)
        {
            v += rng_gauss() * in->noise_mv;
        }
        for (i = 0; i < in->n_spikes; i++)
        {
            if (t >= in->spikes[i].t_ms && t < in->spikes[i].t_ms + in->spikes[i].width_ms)
            {
                v = in->spikes[i].mv;
            }
        }
    }
    if (v < 0.0)
    {
        v = 0.0;
    }
    if (v > VCC_MV)
    {
        v = VCC_MV;
    }
    return v;
}

static void drive_pin(int pin, int level)
{
    pin_input_t *in = &g_inputs[pin];

    if (in->driven_level == level)
    {
        return;
    }
    in->driven_level = level;
    avr_raise_irq(g_pin_irq[pin], (uint32_t)level);
}

static void update_digital(int pin, double t)
{
    pin_input_t *in = &g_inputs[pin];

    if (pin_is_output(pin))
    {
        return;
    }
    if (in_float_window(in, t))
    {
        if (t >= in->float_next_flip_ms)
        {
            in->float_level = rng_uniform() < 0.5 ? 0 : 1;
            in->float_next_flip_ms = t + 1.0 + rng_uniform() * 25.0;
        }
        drive_pin(pin, in->float_level);
        return;
    }
    if (in->has_digital)
    {
        int level = in->driven_level < 0 ? in->initial : in->driven_level;

        while (in->next_event < in->n_events && in->events[in->next_event].t_ms <= t)
        {
            level = in->events[in->next_event].value;
            in->next_event++;
        }
        drive_pin(pin, level);
        return;
    }
    if (pin >= 14 && in->has_analog)
    {
        return; /* analog-driven pin, the ADC IRQ is what matters */
    }
    /* simavr does not model pull-ups, so an undriven input follows PORTx here. */
    drive_pin(pin, pin_pullup_on(pin));
}

static void record_trace(int pin, double t, double mv)
{
    pin_input_t *in = &g_inputs[pin];

    if (!in->bucket_used || mv < in->bucket_min)
    {
        in->bucket_min = mv;
    }
    if (!in->bucket_used || mv > in->bucket_max)
    {
        in->bucket_max = mv;
    }
    in->bucket_used = 1;
    in->last_mv = mv;
    (void)t;
}

static void flush_trace_buckets(double t)
{
    int pin;

    for (pin = 14; pin < NUM_PINS; pin++)
    {
        pin_input_t *in = &g_inputs[pin];

        if (!in->bucket_used || g_n_trace >= MAX_TRACE_POINTS)
        {
            continue;
        }
        g_trace[g_n_trace].t_ms = t;
        g_trace[g_n_trace].pin = pin;
        g_trace[g_n_trace].mv = in->last_mv;
        g_trace[g_n_trace].min_mv = in->bucket_min;
        g_trace[g_n_trace].max_mv = in->bucket_max;
        g_n_trace++;
        in->bucket_used = 0;
    }
}

static avr_cycle_count_t on_tick(struct avr_t *avr, avr_cycle_count_t when, void *param)
{
    double t = now_ms_sim();
    int analog_due = (g_tick_count % ANALOG_EVERY_TICKS) == 0;
    int pin;

    (void)param;
    g_tick_count++;
    for (pin = 0; pin < NUM_PINS; pin++)
    {
        update_digital(pin, t);
    }
    if (analog_due)
    {
        poll_pwm();
        for (pin = 14; pin < NUM_PINS; pin++)
        {
            pin_input_t *in = &g_inputs[pin];

            if (in->has_analog || in->n_floats > 0)
            {
                double mv = analog_value_mv(in, t);

                avr_raise_irq(g_adc_irq[pin - 14], (uint32_t)(mv + 0.5));
                record_trace(pin, t, mv);
            }
        }
    }
    if (t >= g_next_trace_ms)
    {
        flush_trace_buckets(t);
        g_next_trace_ms += TRACE_STEP_MS;
    }
    return when + avr_usec_to_cycles(avr, TICK_US);
}

static void expand_bounce(pin_input_t *in, double t, int value, double bounce_ms, int count)
{
    int i;
    int level = value;
    double tt = t;

    /* A bouncing contact chatters between levels, then settles on the target. */
    for (i = 0; i < count; i++)
    {
        in->events[in->n_events].t_ms = tt;
        in->events[in->n_events].value = level;
        in->n_events++;
        level = !level;
        tt += (bounce_ms / (double)(count > 1 ? count : 1)) * (0.5 + rng_uniform());
    }
    in->events[in->n_events].t_ms = tt;
    in->events[in->n_events].value = value;
    in->n_events++;
}

static int cmp_dig_event(const void *a, const void *b)
{
    const dig_event_t *ea = (const dig_event_t *)a;
    const dig_event_t *eb = (const dig_event_t *)b;

    if (ea->t_ms < eb->t_ms)
    {
        return -1;
    }
    return ea->t_ms > eb->t_ms ? 1 : 0;
}

static char *read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    long n;
    char *buf;

    if (f == NULL)
    {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = malloc((size_t)n + 1);
    if (buf == NULL || fread(buf, 1, (size_t)n, f) != (size_t)n)
    {
        fclose(f);
        free(buf);
        return NULL;
    }
    buf[n] = '\0';
    fclose(f);
    return buf;
}

static double json_num(const cJSON *o, const char *key, double dflt)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, key);

    return cJSON_IsNumber(v) ? v->valuedouble : dflt;
}

static int load_scenario(const char *path, double *duration_ms)
{
    char *text = read_file(path);
    cJSON *root;
    const cJSON *item;
    uint64_t seed;

    if (text == NULL)
    {
        fprintf(stderr, "cannot read scenario %s: %s\n", path, strerror(errno));
        return -1;
    }
    root = cJSON_Parse(text);
    free(text);
    if (root == NULL)
    {
        fprintf(stderr, "scenario is not valid JSON\n");
        return -1;
    }

    *duration_ms = json_num(root, "duration_ms", DEFAULT_SIM_MS);
    seed = (uint64_t)json_num(root, "seed", 1.0);
    g_rng = (seed * 0x9E3779B97F4A7C15ULL) | 1ULL;

    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(root, "analog"))
    {
        const cJSON *pin_j = cJSON_GetObjectItemCaseSensitive(item, "pin");
        const cJSON *seg;
        const cJSON *sp;
        int pin = cJSON_IsString(pin_j) ? parse_pin(pin_j->valuestring) : -1;
        pin_input_t *in;
        const cJSON *segs = cJSON_GetObjectItemCaseSensitive(item, "segments");
        const cJSON *spikes = cJSON_GetObjectItemCaseSensitive(item, "spikes");

        if (pin < 14)
        {
            fprintf(stderr, "analog input needs a pin A0-A5\n");
            continue;
        }
        in = &g_inputs[pin];
        in->has_analog = 1;
        in->noise_mv = json_num(item, "noise_mv", 0.0);
        in->points = calloc((size_t)cJSON_GetArraySize(segs) + 1, sizeof(point_t));
        in->spikes = calloc((size_t)cJSON_GetArraySize(spikes) + 1, sizeof(spike_t));
        cJSON_ArrayForEach(seg, segs)
        {
            in->points[in->n_points].t_ms = json_num(seg, "t_ms", 0.0);
            in->points[in->n_points].mv = json_num(seg, "mv", 0.0);
            in->n_points++;
        }
        cJSON_ArrayForEach(sp, spikes)
        {
            in->spikes[in->n_spikes].t_ms = json_num(sp, "t_ms", 0.0);
            in->spikes[in->n_spikes].width_ms = json_num(sp, "width_ms", 1.0);
            in->spikes[in->n_spikes].mv = json_num(sp, "mv", 0.0);
            in->n_spikes++;
        }
    }

    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(root, "digital"))
    {
        const cJSON *pin_j = cJSON_GetObjectItemCaseSensitive(item, "pin");
        const cJSON *evs = cJSON_GetObjectItemCaseSensitive(item, "events");
        const cJSON *ev;
        int pin = cJSON_IsString(pin_j) ? parse_pin(pin_j->valuestring) : -1;
        pin_input_t *in;
        size_t cap = 2;

        if (pin < 0)
        {
            fprintf(stderr, "digital input has an unknown pin\n");
            continue;
        }
        in = &g_inputs[pin];
        in->has_digital = 1;
        in->initial = (int)json_num(item, "initial", 0.0) ? 1 : 0;
        cJSON_ArrayForEach(ev, evs)
        {
            cap += 2 + (size_t)json_num(ev, "bounce_count", 0.0);
        }
        in->events = calloc(cap, sizeof(dig_event_t));
        cJSON_ArrayForEach(ev, evs)
        {
            double t = json_num(ev, "t_ms", 0.0);
            int value = (int)json_num(ev, "value", 0.0) ? 1 : 0;
            int count = (int)json_num(ev, "bounce_count", 0.0);
            double width = json_num(ev, "bounce_ms", 0.0);

            if (count > 0 && width > 0.0)
            {
                expand_bounce(in, t, value, width, count);
            }
            else
            {
                in->events[in->n_events].t_ms = t;
                in->events[in->n_events].value = value;
                in->n_events++;
            }
        }
        qsort(in->events, (size_t)in->n_events, sizeof(dig_event_t), cmp_dig_event);
    }

    cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(root, "floating"))
    {
        const cJSON *pin_j = cJSON_GetObjectItemCaseSensitive(item, "pin");
        int pin = cJSON_IsString(pin_j) ? parse_pin(pin_j->valuestring) : -1;
        pin_input_t *in;

        if (pin < 0)
        {
            fprintf(stderr, "floating input has an unknown pin\n");
            continue;
        }
        in = &g_inputs[pin];
        in->floats = realloc(in->floats, sizeof(float_window_t) * ((size_t)in->n_floats + 1));
        in->floats[in->n_floats].from_ms = json_num(item, "from_ms", 0.0);
        in->floats[in->n_floats].to_ms = json_num(item, "to_ms", 1e12);
        in->n_floats++;
        in->float_mv = 500.0 + rng_uniform() * 4000.0;
    }

    cJSON_Delete(root);
    return 0;
}

static void write_json_string(FILE *f, const char *s)
{
    const unsigned char *p = (const unsigned char *)s;

    fputc('"', f);
    for (; *p != '\0'; p++)
    {
        if (*p == '"' || *p == '\\')
        {
            fputc('\\', f);
            fputc(*p, f);
        }
        else if (*p < 0x20 || *p >= 0x7F)
        {
            /* Firmware may emit arbitrary bytes, so keep the output plain ASCII. */
            fprintf(f, "\\u%04x", *p);
        }
        else
        {
            fputc(*p, f);
        }
    }
    fputc('"', f);
}

static int write_result(const char *path, const char *exit_reason, double sim_ms, double wall)
{
    char tmp[1024];
    FILE *f;
    int i;
    char name[16];

    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    f = fopen(tmp, "wb");
    if (f == NULL)
    {
        fprintf(stderr, "cannot write %s: %s\n", tmp, strerror(errno));
        return -1;
    }
    fprintf(f, "{\"exit_reason\":\"%s\",\"cycles\":%llu,\"sim_ms\":%.3f,\"wall_ms\":%.1f,",
            exit_reason, (unsigned long long)g_avr->cycle, sim_ms, wall);
    fprintf(f, "\"pin_events_truncated\":%s,\"serial_truncated\":%s,",
            g_pin_events_truncated ? "true" : "false",
            g_lines_truncated ? "true" : "false");

    fprintf(f, "\"serial_log\":[");
    for (i = 0; i < g_n_lines; i++)
    {
        fprintf(f, "%s{\"t_ms\":%.3f,\"text\":", i ? "," : "", g_lines[i].t_ms);
        write_json_string(f, g_lines[i].text);
        fputc('}', f);
    }
    fprintf(f, "],\"pin_events\":[");
    for (i = 0; i < g_n_pin_events; i++)
    {
        pin_name(g_pin_events[i].pin, name, sizeof(name));
        fprintf(f, "%s{\"t_ms\":%.3f,\"pin\":\"%s\",\"value\":%d,\"dir\":\"%s\"}",
                i ? "," : "", g_pin_events[i].t_ms, name, g_pin_events[i].value,
                g_pin_events[i].is_output ? "out" : "in");
    }
    fprintf(f, "],\"pwm_events\":[");
    for (i = 0; i < g_n_pwm_events; i++)
    {
        pin_name(g_pwm_events[i].pin, name, sizeof(name));
        fprintf(f, "%s{\"t_ms\":%.3f,\"pin\":\"%s\",\"duty\":%d}",
                i ? "," : "", g_pwm_events[i].t_ms, name, g_pwm_events[i].duty);
    }
    fprintf(f, "],\"input_trace\":[");
    for (i = 0; i < g_n_trace; i++)
    {
        pin_name(g_trace[i].pin, name, sizeof(name));
        fprintf(f, "%s{\"t_ms\":%.1f,\"pin\":\"%s\",\"mv\":%.1f,\"min_mv\":%.1f,\"max_mv\":%.1f}",
                i ? "," : "", g_trace[i].t_ms, name, g_trace[i].mv,
                g_trace[i].min_mv, g_trace[i].max_mv);
    }
    fprintf(f, "]}\n");
    fclose(f);
    return rename(tmp, path);
}

static void on_sigterm(int sig)
{
    (void)sig;
    g_term_requested = 1;
}

int main(int argc, char **argv)
{
    const char *elf_path = NULL;
    const char *scenario_path = NULL;
    const char *out_path = NULL;
    double wall_limit_ms = DEFAULT_WALL_LIMIT_MS;
    int sim_cap = 1;
    double duration_ms = DEFAULT_SIM_MS;
    elf_firmware_t fw;
    avr_irq_t *uart_out;
    uint32_t uart_flags = 0;
    uint64_t end_cycle;
    const char *exit_reason = "completed";
    double wall_start;
    uint32_t loops = 0;
    int i;

    for (i = 1; i < argc; i++)
    {
        if (strcmp(argv[i], "--elf") == 0 && i + 1 < argc)
        {
            elf_path = argv[++i];
        }
        else if (strcmp(argv[i], "--scenario") == 0 && i + 1 < argc)
        {
            scenario_path = argv[++i];
        }
        else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc)
        {
            out_path = argv[++i];
        }
        else if (strcmp(argv[i], "--wall-limit-ms") == 0 && i + 1 < argc)
        {
            wall_limit_ms = atof(argv[++i]);
        }
        else if (strcmp(argv[i], "--no-sim-cap") == 0)
        {
            sim_cap = 0;
        }
    }
    if (elf_path == NULL || scenario_path == NULL || out_path == NULL)
    {
        fprintf(stderr, "usage: hexharness --elf F --scenario S --out R [--wall-limit-ms N] [--no-sim-cap]\n");
        return 2;
    }

    for (i = 0; i < NUM_PINS; i++)
    {
        g_inputs[i].driven_level = -1;
        g_inputs[i].last_mv = 0.0;
        g_last_level[i] = 0;
        g_last_pwm[i] = -1;
    }
    if (load_scenario(scenario_path, &duration_ms) != 0)
    {
        return 2;
    }
    if (duration_ms > MAX_SIM_MS)
    {
        duration_ms = MAX_SIM_MS;
    }
    if (duration_ms < 1.0)
    {
        duration_ms = 1.0;
    }

    g_pin_events = calloc(MAX_PIN_EVENTS, sizeof(pin_event_t));
    g_pwm_events = calloc(MAX_PWM_EVENTS, sizeof(pwm_event_t));
    g_lines = calloc(MAX_SERIAL_LINES, sizeof(serial_line_t));
    g_trace = calloc(MAX_TRACE_POINTS, sizeof(trace_point_t));
    if (g_pin_events == NULL || g_pwm_events == NULL || g_lines == NULL || g_trace == NULL)
    {
        fprintf(stderr, "out of memory\n");
        return 2;
    }

    memset(&fw, 0, sizeof(fw));
    if (elf_read_firmware(elf_path, &fw) != 0)
    {
        fprintf(stderr, "cannot read ELF %s\n", elf_path);
        return 3;
    }
    strncpy(fw.mmcu, "atmega328p", sizeof(fw.mmcu) - 1);
    fw.frequency = F_CPU_HZ;

    g_avr = avr_make_mcu_by_name(fw.mmcu);
    if (g_avr == NULL)
    {
        fprintf(stderr, "simavr has no atmega328p core\n");
        return 3;
    }
    avr_init(g_avr);
    avr_load_firmware(g_avr, &fw);
    g_avr->frequency = F_CPU_HZ;
    g_avr->vcc = VCC_MV;
    g_avr->avcc = VCC_MV;
    g_avr->aref = VCC_MV;
    g_avr->log = LOG_ERROR;

    /* Default flags would echo to stdout and usleep on every status poll. */
    avr_ioctl(g_avr, AVR_IOCTL_UART_GET_FLAGS('0'), &uart_flags);
    uart_flags &= ~(uint32_t)(AVR_UART_FLAG_STDIO | AVR_UART_FLAG_POOL_SLEEP);
    avr_ioctl(g_avr, AVR_IOCTL_UART_SET_FLAGS('0'), &uart_flags);
    uart_out = avr_io_getirq(g_avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT);
    avr_irq_register_notify(uart_out, on_uart_byte, NULL);

    for (i = 0; i < NUM_PINS; i++)
    {
        uint8_t port;
        uint8_t bit;

        pin_to_port(i, &port, &bit);
        g_pin_ctx[i].pin = i;
        g_pin_ctx[i].port = port;
        g_pin_ctx[i].bit = bit;
        g_pin_irq[i] = avr_io_getirq(g_avr, AVR_IOCTL_IOPORT_GETIRQ(port), bit);
        avr_irq_register_notify(g_pin_irq[i], on_pin_change, &g_pin_ctx[i]);
    }
    for (i = 0; i < 6; i++)
    {
        g_adc_irq[i] = avr_io_getirq(g_avr, AVR_IOCTL_ADC_GETIRQ, ADC_IRQ_ADC0 + i);
    }

    signal(SIGTERM, on_sigterm);

    avr_cycle_timer_register_usec(g_avr, TICK_US, on_tick, NULL);
    /* Apply t=0 inputs before the first instruction runs. */
    on_tick(g_avr, 0, NULL);

    end_cycle = (uint64_t)(duration_ms * ((double)F_CPU_HZ / 1000.0));
    wall_start = wall_ms();

    for (;;)
    {
        int state = avr_run(g_avr);

        if (state == cpu_Crashed || state == cpu_Stopped)
        {
            exit_reason = "crash";
            break;
        }
        if (state == cpu_Done)
        {
            /* simavr stops like this on SLEEP with interrupts off: it can never wake. */
            exit_reason = g_avr->sreg[S_I] ? "crash" : "sleep_deadlock";
            break;
        }
        if (sim_cap && g_avr->cycle >= end_cycle)
        {
            break;
        }
        if ((++loops & 0xFFFFF) == 0)
        {
            if (g_term_requested)
            {
                exit_reason = "timeout";
                break;
            }
            /* In --no-sim-cap mode only the external wall-clock kill can stop this. */
            if (sim_cap && wall_ms() - wall_start > wall_limit_ms)
            {
                exit_reason = "timeout";
                break;
            }
        }
    }
    if (g_line_len > 0)
    {
        g_line_t_ms = now_ms_sim();
        flush_serial_line();
    }
    flush_trace_buckets(now_ms_sim());
    if (write_result(out_path, exit_reason, now_ms_sim(), wall_ms() - wall_start) != 0)
    {
        return 4;
    }
    return 0;
}
