# Loaded by CodeTwin with `ruby -r` before the test runner: records line coverage with Ruby's built-in
# Coverage module (no gem needed) and writes it as LCOV to $CODETWIN_COV_DIR/lcov.info at exit.
require "coverage"
Coverage.start(lines: true)
at_exit do
  dir = ENV["CODETWIN_COV_DIR"]
  if dir
    File.open(File.join(dir, "lcov.info"), "w") do |out|
      Coverage.result.each do |file, data|
        lines = data.is_a?(Hash) ? data[:lines] : data
        next unless lines
        out.puts "SF:#{file}"
        lines.each_with_index { |hits, i| out.puts "DA:#{i + 1},#{hits}" if hits && hits > 0 }
        out.puts "end_of_record"
      end
    end
  end
end
