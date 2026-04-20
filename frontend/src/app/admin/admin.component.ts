import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { LoadBalancerService, LoadBalancerStatus, VmRow } from '../services/load-balancer.service';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css'],
})
export class AdminComponent implements OnInit {
  private readonly lb = inject(LoadBalancerService);

  status: LoadBalancerStatus | null = null;
  loading = false;
  tickLoading = false;
  error: string | null = null;

  readonly maxPerVm = 5;

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading = true;
    this.error = null;
    this.lb.getStatus().subscribe({
      next: (s) => {
        this.status = s;
        this.loading = false;
      },
      error: () => {
        this.error = 'Erreur simulée (ne devrait pas arriver en mode mock).';
        this.loading = false;
      },
    });
  }

  simulateTick(): void {
    this.tickLoading = true;
    this.error = null;
    this.lb.simulateTick().subscribe({
      next: (s) => {
        this.status = s;
        this.tickLoading = false;
      },
      error: () => {
        this.tickLoading = false;
      },
    });
  }

  decisionMessage(s: LoadBalancerStatus): string {
    switch (s.decision) {
      case 'scale_up':
        return 'Scaling UP triggered';
      case 'need_new_vm':
        return 'Need new VM';
      default:
        return 'Stable';
    }
  }

  decisionClass(s: LoadBalancerStatus): string {
    switch (s.decision) {
      case 'scale_up':
        return 'lb-pill lb-pill--warn';
      case 'need_new_vm':
        return 'lb-pill lb-pill--alert';
      default:
        return 'lb-pill lb-pill--ok';
    }
  }

  vmStatusLabel(vm: VmRow): string {
    switch (vm.status) {
      case 'running':
        return 'Running';
      case 'suspended':
        return 'Suspended';
      default:
        return 'Stopped';
    }
  }
}
