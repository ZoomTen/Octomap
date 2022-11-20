ALPHA := 50%

ICONS := \
	open-map.png \
	refresh-map.png \
	save-map.png \
	open-block.png \
	open-gfx.png \
	open-event.png \
	refresh-event.png

all: $(ICONS)

clean:
	rm -v *.png

%-event.png: %-event.svg
	inkscape $< -C --export-type=png -o $@

%.png: %.svg
	inkscape $< -C --export-type=png -o - | magick -background none - -channel A -threshold $(ALPHA) $@
