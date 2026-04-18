import { Component, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { finalize } from 'rxjs';

const API_URL = 'http://localhost:5000/calculate';

/** Fiche équipement Boavizta renvoyée par l’API. */
export interface EquipmentHit {
  name: string;
  co2_kg: number | string;
  manufacturer?: string | null;
  category?: string | null;
  subcategory?: string | null;
  gwp_use_ratio?: number | null;
  yearly_tec?: number | null;
  lifetime?: number | null;
  use_location?: string | null;
  report_date?: string | null;
  sources?: string | null;
  gwp_error_ratio?: number | null;
  gwp_manufacturing_ratio?: number | null;
  weight?: number | null;
  assembly_location?: string | null;
  screen_size?: number | null;
  server_type?: string | null;
  hard_drive?: string | null;
  memory?: string | null;
  number_cpu?: number | null;
  height?: number | null;
  added_date?: string | null;
  add_method?: string | null;
  gwp_transport_ratio?: number | null;
  gwp_eol_ratio?: number | null;
  gwp_electronics_ratio?: number | null;
  gwp_battery_ratio?: number | null;
  gwp_hdd_ratio?: number | null;
  gwp_ssd_ratio?: number | null;
  gwp_othercomponents_ratio?: number | null;
  comment?: string | null;
}

type CalculateResponse = { item: EquipmentHit } | { error: string };

type LegacyMachineResponse = { machine: string; co2_kg: number | string };

/** Ancienne API à deux régions (migration) */
type LegacyFrUsResponse = { fr: EquipmentHit | null; us: EquipmentHit | null };

export type ClimateImage = {
  src: string;
  alt: string;
  caption: string;
};

function parseCo2Kg(raw: unknown): number {
  if (raw === undefined || raw === null || raw === '') return 0;
  if (typeof raw === 'number') return Number.isFinite(raw) ? raw : 0;
  const s = String(raw).trim().replace(/\s/g, '').replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function normalizeToItem(
  res: CalculateResponse | LegacyMachineResponse | LegacyFrUsResponse,
): EquipmentHit | null {
  if ('error' in res && res.error) {
    return null;
  }
  const r = res as Record<string, unknown>;
  if (r['item'] && typeof r['item'] === 'object') {
    return r['item'] as EquipmentHit;
  }
  if (typeof r['machine'] === 'string' && r['co2_kg'] !== undefined) {
    return {
      name: r['machine'] as string,
      co2_kg: r['co2_kg'] as number | string,
    };
  }
  if (r['fr'] !== undefined || r['us'] !== undefined) {
    const fr = r['fr'] as EquipmentHit | null | undefined;
    const us = r['us'] as EquipmentHit | null | undefined;
    return fr ?? us ?? null;
  }
  return null;
}

const DETAIL_FIELDS: { key: keyof EquipmentHit; label: string }[] = [
  { key: 'manufacturer', label: 'Fabricant' },
  { key: 'category', label: 'Catégorie' },
  { key: 'subcategory', label: 'Sous-catégorie' },
  { key: 'use_location', label: 'Lieu d’usage (déclaratif)' },
  { key: 'lifetime', label: 'Durée de vie (ans)' },
  { key: 'yearly_tec', label: 'Électricité annuelle déclarée (kWh/an)' },
  { key: 'gwp_use_ratio', label: 'Part du GWP liée à la phase d’usage' },
  { key: 'gwp_manufacturing_ratio', label: 'Part du GWP — fabrication' },
  { key: 'gwp_transport_ratio', label: 'Part du GWP — transport' },
  { key: 'gwp_eol_ratio', label: 'Part du GWP — fin de vie' },
  { key: 'gwp_electronics_ratio', label: 'Part du GWP — électronique' },
  { key: 'gwp_battery_ratio', label: 'Part du GWP — batterie' },
  { key: 'gwp_hdd_ratio', label: 'Part du GWP — disque dur' },
  { key: 'gwp_ssd_ratio', label: 'Part du GWP — SSD' },
  { key: 'gwp_othercomponents_ratio', label: 'Part du GWP — autres composants' },
  { key: 'gwp_error_ratio', label: 'Part du GWP — incertitude' },
  { key: 'weight', label: 'Masse (kg)' },
  { key: 'assembly_location', label: 'Lieu d’assemblage' },
  { key: 'screen_size', label: 'Taille d’écran (pouces)' },
  { key: 'server_type', label: 'Type serveur' },
  { key: 'hard_drive', label: 'Stockage' },
  { key: 'memory', label: 'Mémoire' },
  { key: 'number_cpu', label: 'Nombre de CPU' },
  { key: 'height', label: 'Hauteur (U ou cm selon fiche)' },
  { key: 'report_date', label: 'Date du rapport' },
  { key: 'added_date', label: 'Date d’ajout en base' },
  { key: 'add_method', label: 'Méthode d’ajout' },
  { key: 'comment', label: 'Commentaire' },
];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './app.html',
  styleUrls: ['./app.css'],
})
export class AppComponent {
  private readonly http = inject(HttpClient);

  machine = '';
  loading = false;
  apiError: string | null = null;
  item: EquipmentHit | null = null;

  readonly suggestions = [
    '13-inch MacBook Air (M1',
    'Latitude 7410',
    'C2422HE Monitor',
  ];

  /** Photos variées : cryosphère, sécheresse, eau, orages, agriculture, feux. */
  readonly climateImages: ClimateImage[] = [
    {
      src: 'https://images.unsplash.com/photo-1444581322113-8d24214367f5?auto=format&fit=crop&w=900&q=82',
      alt: 'Iceberg du glacier Perito Moreno, Argentine',
      caption:
        'Fonte des glaciers et calottes : eau douce, niveau marin et littoraux sous pression — une facette du même réchauffement que le GWP résume en CO₂e.',
    },
    {
      src: 'https://images.unsplash.com/photo-1549885606-bbc17accf949?auto=format&fit=crop&w=900&q=82',
      alt: 'Sol craquelé par la sécheresse',
      caption:
        'Sols desséchés et nappes qui baissent : la chaleur et les pluies plus erratiques fragilisent déjà cultures et approvisionnement en eau.',
    },
    {
      src: 'https://images.unsplash.com/photo-1641118593381-ded30a11d4e1?auto=format&fit=crop&w=900&q=82',
      alt: 'Champ de plantes desséchées sous un ciel clair',
      caption:
        'Récoltes et prairies sous stress : moins d’humidité, canicules plus longues, rendements et élevages exposés.',
    },
    {
      src: 'https://images.unsplash.com/photo-1545276070-ec815f01c6ec?auto=format&fit=crop&w=900&q=82',
      alt: 'Ville et rues inondées sous un ciel nuageux',
      caption:
        'Pluies extrêmes et crues : l’air plus chaud retient plus de vapeur d’eau, ce qui peut démultiplier les épisodes d’inondation.',
    },
    {
      src: 'https://images.unsplash.com/photo-1508697014387-db70aad34f4d?auto=format&fit=crop&w=900&q=82',
      alt: 'Éclair dans un ciel d’orage la nuit',
      caption:
        'Orages et vents violents : une atmosphère plus énergétique alimente déjà des phénomènes météo plus intenses selon les régions.',
    },
    {
      src: 'https://images.unsplash.com/photo-1634009653379-a97409ee15de?auto=format&fit=crop&w=900&q=82',
      alt: 'Incendie de forêt en montagne, flammes et fumée',
      caption:
        'Feux de forêt et sécheresses : forêts et habitations subissent des saisons de feu plus longues et plus destructrices.',
    },
  ];

  co2Kg(): number {
    return parseCo2Kg(this.item?.co2_kg);
  }

  get displayTitle(): string {
    return this.item?.name ?? '';
  }

  detailRows(): { label: string; value: string }[] {
    if (!this.item) return [];
    const out: { label: string; value: string }[] = [];
    for (const { key, label } of DETAIL_FIELDS) {
      const raw = this.item[key];
      if (raw === undefined || raw === null || raw === '') continue;
      out.push({ label, value: this.formatDetailValue(key, raw) });
    }
    return out;
  }

  formatDetailValue(key: keyof EquipmentHit, raw: unknown): string {
    if (raw === null || raw === undefined) return '';
    if (typeof raw === 'string') return raw;
    const n = Number(raw);
    if (!Number.isFinite(n)) return String(raw);
    if (String(key).includes('ratio') && n >= 0 && n <= 1) {
      return `${Math.round(n * 1000) / 10} %`;
    }
    if (Number.isInteger(n) || Math.abs(n - Math.round(n)) < 1e-6) {
      return String(Math.round(n));
    }
    return String(n);
  }

  pickSuggestion(text: string): void {
    this.machine = text;
    this.calculate();
  }

  calculate(): void {
    const q = this.machine
      .trim()
      .replace(/^["'«»]+|["'«»]+$/g, '');
    if (!q) {
      this.apiError = 'Indique un modèle ou une partie du nom de la machine.';
      this.item = null;
      return;
    }

    this.loading = true;
    this.apiError = null;
    this.item = null;

    this.http
      .post<CalculateResponse | LegacyMachineResponse | LegacyFrUsResponse>(API_URL, {
        machine: q,
      })
      .pipe(finalize(() => (this.loading = false)))
      .subscribe({
        next: (res) => {
          if ('error' in res && res.error) {
            this.apiError =
              res.error === 'machine not found'
                ? 'Aucune correspondance dans notre base Boavizta. Essaie un autre mot-clé (ex. marque + modèle).'
                : res.error;
            return;
          }
          const it = normalizeToItem(res);
          if (!it) {
            this.apiError =
              'Réponse API inattendue. Reconstruis le backend et la base (docker compose down -v puis up --build).';
            return;
          }
          this.item = it;
        },
        error: (err: HttpErrorResponse) => {
          if (err.status === 404 && err.error && typeof err.error === 'object') {
            const body = err.error as { error?: string };
            const code = body.error;
            this.apiError =
              code === 'machine not found'
                ? 'Aucune correspondance dans notre base Boavizta. Essaie un autre mot-clé (ex. marque + modèle).'
                : code ?? 'Ressource introuvable.';
            return;
          }
          if (err.status === 0) {
            this.apiError =
              'Connexion impossible (réseau ou CORS). Vérifie que le backend tourne sur le port 5000.';
            return;
          }
          this.apiError =
            'Impossible de joindre l’API. Vérifie que le backend tourne (port 5000).';
        },
      });
  }
}
