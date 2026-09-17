#include "SGSystem.h"
#include <libproc.h>
#include <sys/proc_info.h>
#include <sys/resource.h>
#include <sys/sysctl.h>
#include <mach/mach.h>
#include <mach/mach_time.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>

static uint64_t cpu_tick_frequency;
static pthread_once_t clock_once = PTHREAD_ONCE_INIT;
static void initialize_cpu_clock(void) {
    // This hardware clock is not virtualized to 1:1 by Rosetta's mach_timebase_info.
    size_t size = sizeof cpu_tick_frequency;
    if (sysctlbyname("hw.tbfrequency", &cpu_tick_frequency, &size, NULL, 0) != 0) cpu_tick_frequency = 0;
}

int sg_pids(int32_t *buffer, int capacity) {
    int size = proc_listpids(PROC_ALL_PIDS, 0, buffer, capacity * (int)sizeof(int32_t));
    return size > 0 ? size / (int)sizeof(int32_t) : 0;
}
int sg_read_process(int32_t pid, sg_process *out) {
    struct proc_bsdinfo bsd = {0};
    struct proc_taskinfo task = {0};
    if (proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &bsd, sizeof bsd) != sizeof bsd) return 0;
    if (proc_pidinfo(pid, PROC_PIDTASKINFO, 0, &task, sizeof task) != sizeof task) return 0;
    memset(out, 0, sizeof *out);
    out->pid = pid; out->parent_pid = bsd.pbi_ppid; out->uid = bsd.pbi_uid;
    out->start_usec = bsd.pbi_start_tvsec * 1000000ULL + bsd.pbi_start_tvusec;
    // proc_taskinfo reports hardware Mach ticks, including when this reader runs under Rosetta.
    pthread_once(&clock_once, initialize_cpu_clock);
    if (cpu_tick_frequency == 0) return 0;
    out->cpu_nsec = (uint64_t)(((__uint128_t)task.pti_total_user + task.pti_total_system) * 1000000000ULL / cpu_tick_frequency);
    out->resident_bytes = task.pti_resident_size;
    snprintf(out->name, sizeof out->name, "%s", bsd.pbi_name[0] ? bsd.pbi_name : bsd.pbi_comm);
    proc_pidpath(pid, out->path, sizeof out->path);
    struct rusage_info_v2 usage = {0};
    if (proc_pid_rusage(pid, RUSAGE_INFO_V2, (rusage_info_t *)&usage) == 0) {
        out->read_bytes = usage.ri_diskio_bytesread;
        out->write_bytes = usage.ri_diskio_byteswritten;
        out->io_available = 1;
    }
    // Do not associate counters with a PID that was recycled during collection.
    struct proc_bsdinfo after = {0};
    if (proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &after, sizeof after) != sizeof after) return 0;
    return bsd.pbi_start_tvsec == after.pbi_start_tvsec && bsd.pbi_start_tvusec == after.pbi_start_tvusec;
}
int sg_read_host(sg_host *out) {
    memset(out, 0, sizeof *out);
    host_cpu_load_info_data_t cpu;
    mach_msg_type_number_t count = HOST_CPU_LOAD_INFO_COUNT;
    mach_port_t host = mach_host_self();
    if (host_statistics(host, HOST_CPU_LOAD_INFO, (host_info_t)&cpu, &count) != KERN_SUCCESS) {
        mach_port_deallocate(mach_task_self(), host); return 0;
    }
    out->user_ticks = cpu.cpu_ticks[CPU_STATE_USER];
    out->system_ticks = cpu.cpu_ticks[CPU_STATE_SYSTEM];
    out->idle_ticks = cpu.cpu_ticks[CPU_STATE_IDLE];
    out->nice_ticks = cpu.cpu_ticks[CPU_STATE_NICE];
    size_t size = sizeof out->memory_total;
    sysctlbyname("hw.memsize", &out->memory_total, &size, NULL, 0);
    vm_statistics64_data_t vm;
    count = HOST_VM_INFO64_COUNT;
    vm_size_t pagesize;
    if (host_page_size(host, &pagesize) == KERN_SUCCESS &&
        host_statistics64(host, HOST_VM_INFO64, (host_info64_t)&vm, &count) == KERN_SUCCESS) {
        // Working memory, not a claim to reproduce Activity Monitor's memory pressure.
        out->memory_used = ((uint64_t)vm.active_count + vm.wire_count + vm.compressor_page_count) * pagesize;
        out->memory_available = 1;
    }
    mach_port_deallocate(mach_task_self(), host);
    return 1;
}
