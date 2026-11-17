function run_multi_msb_huffman_batch(list_file, output_csv, recovery_dir)
% Execute the pinned upstream Multi-MSB/Huffman implementation without editing it.
% The only driver correction is passing the actually embedded bit count to
% Extract_Data/Recover_Image; upstream Main.m incorrectly passes the request size.
  pkg load statistics;
  addpath(fileparts(mfilename('fullpath')));
  list_fid = fopen(list_file, 'r');
  if list_fid < 0, error('Cannot open input list: %s', list_file); end
  out_fid = fopen(output_csv, 'w');
  if out_fid < 0, fclose(list_fid); error('Cannot open CSV: %s', output_csv); end
  if ~exist(recovery_dir, 'dir'), mkdir(recovery_dir); end
  fprintf(out_fid, 'image_id,attempted_bits,embedded_bits,method_native_net_bpp,payload_exact,image_exact,runtime_s,status,error\n');
  while true
    image_path = fgetl(list_fid);
    if ~ischar(image_path), break; end
    image_path = strtrim(image_path);
    if isempty(image_path), continue; end
    [~, image_id, ~] = fileparts(image_path);
    attempted_bits = 0; embedded_bits = 0; native_bpp = NaN;
    payload_exact = false; image_exact = false; status = 'ERROR'; error_text = '';
    t0 = tic();
    try
      source = imread(image_path);
      if ndims(source) ~= 2 || ~isa(source, 'uint8')
        error('Unsupported input: expected native 2-D uint8 grayscale');
      end
      origin_I = double(source);
      [row, col] = size(origin_I);
      attempted_bits = 8 * row * col;
      rand('seed', 0);
      D = round(rand(1, attempted_bits) * 1);
      Image_key = 1; Data_key = 2; ref_x = 1; ref_y = 1;
      [encrypt_I, stego_I, emD] = Encrypt_Embed(origin_I, D, Image_key, Data_key, ref_x, ref_y);
      embedded_bits = length(emD);
      native_bpp = embedded_bits / (row * col);
      if embedded_bits > 0
        % The upstream Main.m passes attempted_bits here. The extractor's
        % contract is the number of bits actually embedded, returned as emD.
        [Side_Information, Refer_Value, Encrypt_exD, Map_I, sign] = ...
          Extract_Data(stego_I, embedded_bits, ref_x, ref_y);
        if sign == 1
          exD = Encrypt_Data(Encrypt_exD, Data_key);
          payload_exact = isequal(reshape(emD, 1, []), reshape(exD, 1, []));
          recovered_I = Recover_Image(stego_I, Image_key, Side_Information, ...
            Refer_Value, Map_I, embedded_bits, ref_x, ref_y);
          image_exact = isequal(origin_I, recovered_I);
          if image_exact
            imwrite(uint8(recovered_I), fullfile(recovery_dir, [image_id '_recovered.png']));
          end
          if payload_exact && image_exact
            status = 'PASS';
          else
            status = 'ROUNDTRIP_FAIL';
          end
        else
          status = 'EXTRACTION_INCOMPLETE';
          error_text = 'Original Extract_Data could not decode the complete embedded stream';
        end
      else
        status = 'NO_CAPACITY';
        error_text = 'Upstream Embed_Data returned zero embedded payload bits';
      end
    catch err
      status = 'ERROR';
      error_text = strrep(strrep(err.message, ',', ';'), sprintf('\n'), ' ');
    end
    runtime_s = toc(t0);
    fprintf(out_fid, '"%s",%.0f,%.0f,%.12g,%d,%d,%.6f,"%s","%s"\n', ...
      image_id, attempted_bits, embedded_bits, native_bpp, payload_exact, ...
      image_exact, runtime_s, status, error_text);
    fflush(out_fid);
    fprintf('MULTI_MSB %s %s bits=%.0f bpp=%.6f %.2fs\n', ...
      image_id, status, embedded_bits, native_bpp, runtime_s);
  end
  fclose(list_fid);
  fclose(out_fid);
end