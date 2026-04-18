import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { delay } from 'rxjs/operators';

/** Simule GET /api/status — aucun appel HTTP réel. */
export type VmStatus = 'running' | 'suspended' | 'stopped';
export type ContainerType = 'frontend' | 'backend' | 'postgres';
export type ContainerStatus = 'running' | 'stopped';
export type LbDecision = 'scale_up' | 'need_new_vm' | 'stable';

export interface VmRow {
  id: string;
  status: VmStatus;
  containers: number;
  cpu: number;
  ram: number;
}

export interface ContainerRow {
  id: string;
  type: ContainerType;
  status: ContainerStatus;
  vm: string;
}

export interface LoadBalancerStatus {
  requests_per_minute: number;
  active_apps: number;
  vms: VmRow[];
  containers: ContainerRow[];
  decision: LbDecision;
}

const MAX_CONTAINERS_PER_VM = 5;

@Injectable({ providedIn: 'root' })
export class LoadBalancerService {
  /** Simule GET /api/status (données mock, léger délai réseau fictif). */
  getStatus(): Observable<LoadBalancerStatus> {
    return of(this.buildSnapshot(this.defaultVms(), this.defaultContainers(), 4, 2)).pipe(delay(180));
  }

  /** Régénère l’état pour un « tick » orchestrateur (démo). */
  simulateTick(): Observable<LoadBalancerStatus> {
    return of(this.randomSnapshot()).pipe(delay(320));
  }

  private defaultVms(): VmRow[] {
    return [
      { id: 'vm-1', status: 'running', containers: 3, cpu: 45, ram: 60 },
      { id: 'vm-2', status: 'running', containers: 2, cpu: 30, ram: 40 },
      { id: 'vm-3', status: 'suspended', containers: 0, cpu: 0, ram: 0 },
    ];
  }

  private defaultContainers(): ContainerRow[] {
    return [
      { id: 'c1', type: 'frontend', status: 'running', vm: 'vm-1' },
      { id: 'c2', type: 'backend', status: 'running', vm: 'vm-1' },
      { id: 'c4', type: 'postgres', status: 'running', vm: 'vm-1' },
      { id: 'c3', type: 'postgres', status: 'running', vm: 'vm-2' },
    ];
  }

  private buildSnapshot(
    vms: VmRow[],
    containers: ContainerRow[],
    rpm: number,
    activeApps: number,
  ): LoadBalancerStatus {
    const vmsSynced = this.syncVmContainerCounts(vms, containers);
    const s: LoadBalancerStatus = {
      requests_per_minute: rpm,
      active_apps: activeApps,
      vms: vmsSynced,
      containers,
      decision: 'stable',
    };
    s.decision = this.computeDecision(s);
    return s;
  }

  private randomSnapshot(): LoadBalancerStatus {
    const vmCount = 3 + Math.floor(Math.random() * 3);
    const vmIds = Array.from({ length: vmCount }, (_, i) => `vm-${i + 1}`);
    const statuses: VmStatus[] = ['running', 'running', 'suspended', 'stopped'];
    const vms: VmRow[] = vmIds.map((id, i) => {
      const st = statuses[Math.floor(Math.random() * statuses.length)] as VmStatus;
      const running = st === 'running';
      return {
        id,
        status: st,
        containers: 0,
        cpu: running ? Math.floor(Math.random() * 85) + 10 : 0,
        ram: running ? Math.floor(Math.random() * 80) + 15 : 0,
      };
    });

    const types: ContainerType[] = ['frontend', 'backend', 'postgres'];
    const nContainers = Math.min(12, 2 + Math.floor(Math.random() * 8));
    const containers: ContainerRow[] = [];
    for (let i = 0; i < nContainers; i++) {
      const vm = vmIds[Math.floor(Math.random() * vmIds.length)];
      const running = Math.random() > 0.15;
      containers.push({
        id: `c${i + 1}`,
        type: types[i % types.length],
        status: running ? 'running' : 'stopped',
        vm,
      });
    }

    const rpm = Math.floor(Math.random() * 10);
    const activeApps = Math.min(5, 1 + Math.floor(Math.random() * 4));
    return this.buildSnapshot(vms, containers, rpm, activeApps);
  }

  private syncVmContainerCounts(vms: VmRow[], containers: ContainerRow[]): VmRow[] {
    const counts = new Map<string, number>();
    for (const c of containers) {
      if (c.status === 'running') {
        counts.set(c.vm, (counts.get(c.vm) ?? 0) + 1);
      }
    }
    return vms.map((vm) => ({
      ...vm,
      containers: counts.get(vm.id) ?? 0,
    }));
  }

  /**
   * Règles démo (UI) :
   * - VM saturée (≥ 5 conteneurs actifs) → need_new_vm
   * - sinon charge > 2 req/min → scale_up
   * - sinon stable
   */
  computeDecision(s: LoadBalancerStatus): LbDecision {
    const anyVmFull = s.vms.some((vm) => vm.containers >= MAX_CONTAINERS_PER_VM);
    if (anyVmFull) return 'need_new_vm';
    if (s.requests_per_minute > 2) return 'scale_up';
    return 'stable';
  }
}
