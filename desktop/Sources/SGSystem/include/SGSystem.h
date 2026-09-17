#ifndef SG_SYSTEM_H
#define SG_SYSTEM_H
#include <stdint.h>
typedef struct {
    int32_t pid, parent_pid;
    uint32_t uid;
    uint64_t start_usec, cpu_nsec, resident_bytes, read_bytes, write_bytes;
    int io_available;
    char name[256];
    char path[4096];
} sg_process;
typedef struct {
    uint64_t user_ticks, system_ticks, idle_ticks, nice_ticks;
    uint64_t memory_used, memory_total;
    int memory_available;
} sg_host;
int sg_pids(int32_t *buffer, int capacity);
int sg_read_process(int32_t pid, sg_process *result);
int sg_read_host(sg_host *result);
#endif
