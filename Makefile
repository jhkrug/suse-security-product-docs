.PHONY: all
all:
	@echo "Available targets:"
	@echo "  product-local              Build the local product docs site for local workstation test"
	@echo "  product-remote             Build the remote product docs site (as would happen on GH)"
	@echo "  preview                    Preview the local product docs site"
	@echo "  dev                        Rebuild on file change and live-reload the browser"
	@echo "  clean                      Clean build artifacts"
	@echo "  checkmake                  Check Makefile for common issues"
	@echo "  check-versions             Check the documentation version markers"
	@echo "  environment                Set up the Node.js environment"
	@echo "  tmpdir                     Create temporary directories"

.PHONY: product-local
product-local: tmpdir environment build-product-local

.PHONY: build-product-local
build-product-local:
	npx antora --version | tee tmp/build.log
	npx antora --stacktrace --log-format=pretty --log-level=info \
		local-product-playbook.yml \
		2>&1 | tee -a tmp/build.log
	$(MAKE) post-process
	@echo ""
	@echo "If your build was successful, you can preview the site with"
	@echo "'make preview'."
	@echo ""

.PHONY: product-remote
product-remote: tmpdir environment
	npx antora --version | tee tmp/build.log
	npx antora --stacktrace --log-format=pretty --log-level=info \
		remote-product-playbook.yml \
		2>&1 | tee -a tmp/build.log
	$(MAKE) post-process

# Split the Lunr search index into one index for each language, and move
# the sitemaps out of the way.
.PHONY: post-process
post-process:
	cp build/site/search-index.js tmp/.
	node product-docs-common/jscript/split-search-index.js build/site/search-index.js build/site/lang-indexes
	mkdir -p build/site/sitemaps.not-used
	find build/site -type f -name "sitemap*.xml" -exec sh -c 'mv "$$0" "$${0%.xml}.xml-not-used"' {} \;
	mv build/site/*.xml-not-used build/site/sitemaps.not-used/. > /dev/null 2>&1 || true
	gzip build/site/sitemaps.not-used/*.xml-not-used > /dev/null 2>&1 || true

.PHONY: clean
clean:
	rm -rf build*
	rm -rf tmp/*.log

NPM_FLAGS = --no-color --no-progress
.PHONY: environment
environment:
	npm $(NPM_FLAGS) ci || npm $(NPM_FLAGS) install

.PHONY: tmpdir
tmpdir:
	mkdir -p tmp

.PHONY: checkmake
checkmake:
	@if [ $$(which checkmake 2>/dev/null) ]; then \
		checkmake --config=tmp/checkmake.ini Makefile; \
		if [ $$? -ne 0 ]; then echo "checkmake failed"; exit 1; \
		else echo "checkmake passed"; \
		fi; \
	else echo "checkmake not available"; fi

.PHONY: check-versions
check-versions:
	./scripts/check-docs-versions.sh

.PHONY: preview
preview:
	npx http-server build/site -c-1

.PHONY: dev
dev: tmpdir environment
	touch tmp/reload-stamp
	npx nodemon \
		--watch docs --watch shared \
		--watch local-product-playbook.yml \
		--ext adoc,yml,hbs,css,js,svg,png \
		--delay 1 \
		--exec "$(MAKE) build-product-local && touch tmp/reload-stamp" & \
	NODEMON_PID=$$!; \
	trap 'kill $$NODEMON_PID 2>/dev/null' EXIT INT TERM; \
	npx browser-sync start \
		--server build/site \
		--files tmp/reload-stamp \
		--no-open --no-ui --no-notify \
		--port 8080

.PHONY: test
test:
