% RPCA via Inexact ALM -- Octave port of tools/compare_separation_methods.py::_rpca_ialm
% Reads mag_f32.bin (float32, C-order [m,n]) + meta.json, writes L/S + stats.
% Parameters are identical to the numpy reference:
%   lam = 1/sqrt(max(m,n)), Y = M/norm2(M), mu = 1.25/norm2(M), rho = 1.5,
%   tol = 1e-6 (fro(Z)/fro(M)), max_iter = 120.

pkg load audio;

base = 'D:\FYP_HKBU_runs\rerun_20261030_2358\rpca_octave';
meta_txt = fileread(fullfile(base, 'meta.json'));
m = str2double(regexp(meta_txt, '"shape":\s*\[\s*(\d+)', 'tokens', 'once'){1});
n = str2double(regexp(meta_txt, '"shape":\s*\[\s*\d+,\s*(\d+)', 'tokens', 'once'){1});
printf('mag %d x %d\n', m, n);

fid = fopen(fullfile(base, 'mag_f32.bin'), 'rb');
M = fread(fid, [n, m], 'float32');   % C-order [m,n] read as [n,m] then transpose
fclose(fid);
M = double(M');
printf('loaded %.2f MB\n', numel(M) * 8 / 1e6);

tic;
lam = 1.0 / sqrt(max(m, n));
nrm = max(norm(M, 2), eps);
Y = M / nrm;
mu = 1.25 / nrm;
rho = 1.5;
L = zeros(m, n);
S = zeros(m, n);
fM = norm(M, 'fro') + eps;
iters = 0;
resid = [];
for k = 1:120
  [U, sig, V] = svd(M - S + Y / mu, 'econ');
  sig = diag(sig);
  L = U * diag(max(sig - 1.0 / mu, 0)) * V';
  T = M - L + Y / mu;
  S = sign(T) .* max(abs(T) - lam / mu, 0);
  Z = M - L - S;
  Y = Y + mu * Z;
  r = norm(Z, 'fro') / fM;
  resid(end + 1) = r;
  iters = k;
  if r < 1e-6
    break;
  end
  mu = mu * rho;
end
elapsed = toc;

fid = fopen(fullfile(base, 'L_f32.bin'), 'wb');
fwrite(fid, L', 'float32');
fclose(fid);
fid = fopen(fullfile(base, 'S_f32.bin'), 'wb');
fwrite(fid, S', 'float32');
fclose(fid);

Sm = abs(S);
Lm = abs(L);
mask = min(max(Sm ./ (Sm + Lm + eps), 0), 1);
fid = fopen(fullfile(base, 'mask_f32.bin'), 'wb');
fwrite(fid, mask', 'float32');
fclose(fid);

fid = fopen(fullfile(base, 'octave_stats.txt'), 'w');
fprintf(fid, 'iters=%d\n', iters);
fprintf(fid, 'elapsed_s=%.3f\n', elapsed);
fprintf(fid, 'final_rel_resid=%.9e\n', resid(end));
fprintf(fid, 'lam=%.9e\n', lam);
fprintf(fid, 'mu0_norm=%.9e\n', mu / (rho ^ iters));
fprintf(fid, 'norm2_M=%.9e\n', nrm);
fprintf(fid, 'fro_M=%.9e\n', fM);
fprintf(fid, 'max_S=%.6f\n', max(S(:)));
fprintf(fid, 'max_L=%.6f\n', max(L(:)));
fprintf(fid, 'mask_mean=%.6f\n', mean(mask(:)));
fclose(fid);

printf('DONE iters=%d elapsed=%.2fs rel_resid=%.3e\n', iters, elapsed, resid(end));
printf('OCTAVE_OK\n');
